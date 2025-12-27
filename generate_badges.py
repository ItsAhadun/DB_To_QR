"""
Badge PDF Generator Script
Generates separate PDFs for Private Delegates and Delegations.

Dependencies: pip install reportlab qrcode pillow
"""

import csv
import io
from collections import defaultdict

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def load_entities(filepath: str) -> dict:
    """
    Load entities from CSV into a dictionary.
    Key = entity_id
    Value = dict with 'entity_type' and 'display_name' (team_name or institution_name)
    """
    entities = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_id = row['entity_id'].strip()
            entity_type = row.get('entity_type', '').strip()
            team_name = row.get('team_name', '').strip()
            institution_name = row.get('institution_name', '').strip()
            
            # Use team_name if available, otherwise institution_name
            display_name = team_name if team_name else institution_name
            
            entities[entity_id] = {
                'entity_type': entity_type,
                'display_name': display_name
            }
    return entities


def load_participants(filepath: str) -> dict:
    """
    Load participants from CSV and group by entity_id.
    Returns: dict where key = entity_id, value = list of participant dicts
    """
    participants_by_entity = defaultdict(list)
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entity_id = row['entity_id'].strip()
            participant = {
                'participant_id': row.get('participant_id', '').strip(),
                'name': row.get('name', '').strip()
            }
            participants_by_entity[entity_id].append(participant)
    return dict(participants_by_entity)


def generate_qr_code(data: str, box_size: int = 10) -> ImageReader:
    """
    Generate a QR code image for the given data.
    Returns an ImageReader object suitable for reportlab.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes for reportlab
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return ImageReader(buffer)


def generate_badges_pdf(
    entities: dict,
    participants_by_entity: dict,
    output_file: str,
    pdf_title: str = "Badges",
    group_all_together: bool = False
):
    """
    Generate a PDF file with QR code badges.
    
    PDF Configuration:
    - Page Size: A4 (Portrait)
    - Margins: 10mm
    - Grid Layout: Calculated to fit 40mm x 40mm QR codes with 10mm text space below
    
    Args:
        entities: Dictionary of entity information
        participants_by_entity: Dictionary mapping entity_id to list of participants
        output_file: Output PDF file path
        pdf_title: Title for console output
        group_all_together: If True, all participants are grouped together in a continuous
                           grid (for Private Delegates). If False, each entity starts on 
                           a new page (for Delegations).
    """
    if not participants_by_entity:
        print(f"No participants to process for {output_file}")
        return
    
    # PDF Configuration
    page_width, page_height = A4  # A4 is 210mm x 297mm
    margin = 10 * mm
    
    # Badge dimensions
    qr_size = 40 * mm
    text_space = 10 * mm
    badge_width = qr_size
    badge_height = qr_size + text_space
    
    # Footer space (for entity info at bottom of page)
    footer_height = 15 * mm
    
    # Calculate usable area
    usable_width = page_width - (2 * margin)
    usable_height = page_height - (2 * margin) - footer_height
    
    # Calculate grid dimensions
    cols = int(usable_width // badge_width)
    rows = int(usable_height // badge_height)
    badges_per_page = cols * rows
    
    # Calculate spacing to center the grid
    total_badge_width = cols * badge_width
    total_badge_height = rows * badge_height
    h_spacing = (usable_width - total_badge_width) / (cols + 1) if cols > 1 else 0
    v_spacing = (usable_height - total_badge_height) / (rows + 1) if rows > 1 else 0
    
    # Create PDF canvas
    c = canvas.Canvas(output_file, pagesize=A4)
    
    def draw_footer(footer_text: str):
        """Draw footer text at the bottom of the page."""
        c.setFont("Helvetica-Bold", 10)
        footer_y = margin
        c.drawCentredString(page_width / 2, footer_y, footer_text)
    
    def draw_entity_footer(entity_id: str, entity_info: dict):
        """Draw entity information at the bottom of the page."""
        c.setFont("Helvetica-Bold", 10)
        footer_y = margin
        
        display_name = entity_info.get('display_name', 'Unknown')
        
        # Draw entity_id and display_name centered at bottom
        footer_text = f"{entity_id}"
        c.drawCentredString(page_width / 2, footer_y + 5 * mm, footer_text)
        
        c.setFont("Helvetica", 9)
        c.drawCentredString(page_width / 2, footer_y, display_name)
    
    def draw_badge(participant: dict, badge_index: int):
        """Draw a single badge at the specified grid position."""
        # Calculate position in grid
        col = badge_index % cols
        row = badge_index // cols
        
        # Calculate x and y position (top-left of badge)
        x = margin + h_spacing + col * (badge_width + h_spacing)
        # Y from top, but reportlab uses bottom-left origin
        y_from_top = margin + footer_height + v_spacing + row * (badge_height + v_spacing)
        y = page_height - y_from_top - badge_height
        
        # Generate and draw QR code
        participant_id = participant['participant_id']
        if participant_id:
            qr_image = generate_qr_code(participant_id)
            c.drawImage(qr_image, x, y + text_space, width=qr_size, height=qr_size)
        
        # Draw participant name centered below QR code
        participant_name = participant['name']
        c.setFont("Helvetica", 7)
        
        # Truncate name if too long
        max_name_length = 25
        if len(participant_name) > max_name_length:
            participant_name = participant_name[:max_name_length - 3] + "..."
        
        name_x = x + (qr_size / 2)
        name_y = y + (text_space / 2)
        c.drawCentredString(name_x, name_y, participant_name)
    
    if group_all_together:
        # Group all participants together in a continuous grid
        # (Used for Private Delegates)
        draw_footer("Private Delegates")
        
        badge_index = 0
        
        for entity_id, participants in participants_by_entity.items():
            for participant in participants:
                # Check if we need a new page
                if badge_index >= badges_per_page:
                    c.showPage()
                    draw_footer("Private Delegates")
                    badge_index = 0
                
                draw_badge(participant, badge_index)
                badge_index += 1
        
        # Finalize last page
        c.showPage()
    else:
        # Each entity gets its own page(s)
        # (Used for Delegations)
        for entity_id, participants in participants_by_entity.items():
            # Get entity info (use defaults if not found)
            entity_info = entities.get(entity_id, {
                'entity_type': 'Unknown',
                'display_name': 'Unknown Delegation'
            })
            
            # Start a new page for each entity
            draw_entity_footer(entity_id, entity_info)
            
            badge_index = 0
            
            for participant in participants:
                # Check if we need a new page
                if badge_index >= badges_per_page:
                    c.showPage()
                    draw_entity_footer(entity_id, entity_info)
                    badge_index = 0
                
                draw_badge(participant, badge_index)
                badge_index += 1
            
            # Move to next page for the next entity
            c.showPage()
    
    # Save the PDF
    c.save()
    print(f"\n{pdf_title}:")
    print(f"  PDF generated: {output_file}")
    print(f"  Entities processed: {len(participants_by_entity)}")
    total_participants = sum(len(p) for p in participants_by_entity.values())
    print(f"  Total participants: {total_participants}")


def main():
    """
    Main function to generate separate PDFs for:
    1. Private Delegates
    2. Delegations (Regular Delegation, Junior Delegation, etc.)
    """
    # File paths
    entities_file = 'data/entities_upload.csv'
    participants_file = 'data/participants_upload.csv'
    
    # Output files
    private_delegates_pdf = 'badges_private_delegates.pdf'
    delegations_pdf = 'badges_delegations.pdf'
    
    # Load all data
    print("Loading data...")
    entities = load_entities(entities_file)
    all_participants = load_participants(participants_file)
    
    # Separate entities by type
    private_delegate_entities = {}
    delegation_entities = {}
    
    for entity_id, entity_info in entities.items():
        entity_type = entity_info.get('entity_type', '').lower()
        if 'private delegate' in entity_type:
            private_delegate_entities[entity_id] = entity_info
        else:
            delegation_entities[entity_id] = entity_info
    
    # Separate participants by entity type
    private_delegate_participants = {}
    delegation_participants = {}
    
    for entity_id, participants in all_participants.items():
        entity_info = entities.get(entity_id, {})
        entity_type = entity_info.get('entity_type', '').lower()
        
        if 'private delegate' in entity_type:
            private_delegate_participants[entity_id] = participants
        else:
            delegation_participants[entity_id] = participants
    
    print(f"\nFound {len(private_delegate_entities)} Private Delegate entities")
    print(f"Found {len(delegation_entities)} Delegation entities")
    
    # Generate PDFs
    print("\n" + "="*50)
    print("Generating PDFs...")
    print("="*50)
    
    # Generate Private Delegates PDF
    generate_badges_pdf(
        entities=entities,
        participants_by_entity=private_delegate_participants,
        output_file=private_delegates_pdf,
        pdf_title="Private Delegates PDF",
        group_all_together=True  # Group all private delegates together in grid
    )
    
    # Generate Delegations PDF
    generate_badges_pdf(
        entities=entities,
        participants_by_entity=delegation_participants,
        output_file=delegations_pdf,
        pdf_title="Delegations PDF"
    )
    
    print("\n" + "="*50)
    print("All PDFs generated successfully!")
    print("="*50)


if __name__ == '__main__':
    main()
