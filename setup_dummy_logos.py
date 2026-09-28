from PIL import Image, ImageDraw, ImageFont

def create_dummy_logo(text, filename, width=200, height=200, bg_color='white', text_color='green'):
    img = Image.new('RGB', (width, height), color=bg_color)
    d = ImageDraw.Draw(img)
    
    # Try to use a default font, otherwise use whatever is available
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        font = ImageFont.load_default()
        
    text_bbox = d.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    x = (width - text_width) / 2
    y = (height - text_height) / 2
    
    d.text((x, y), text, fill=text_color, font=font)
    
    # Draw a circle around it
    d.ellipse([10, 10, width-10, height-10], outline=text_color, width=5)
    
    img.save(filename)

if __name__ == '__main__':
    create_dummy_logo('BMI Logo', 'bmi_logo.png')
    print("Created dummy logo bmi_logo.png")
