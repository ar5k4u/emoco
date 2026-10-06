import os
from PIL import Image
import shutil
import subprocess

def make_icns(src_path, dest_icns):
    iconset_dir = 'src/artisan.iconset'
    if os.path.exists(iconset_dir):
        shutil.rmtree(iconset_dir)
    os.makedirs(iconset_dir)

    img = Image.open(src_path)
    
    # Sizes required by iconutil
    # filename format: icon_{size}x{size}{@2x}.png
    # size is the point size. @2x is double pixels.
    # 16x16, 16x16@2x (32)
    # 32x32, 32x32@2x (64)
    # 128x128, 128x128@2x (256)
    # 256x256, 256x256@2x (512)
    # 512x512, 512x512@2x (1024)
    
    sizes = [
        (16, ''), (16, '@2x'),
        (32, ''), (32, '@2x'),
        (128, ''), (128, '@2x'),
        (256, ''), (256, '@2x'),
        (512, ''), (512, '@2x')
    ]

    for size_pt, suffix in sizes:
        pixel_size = size_pt * (2 if '@2x' in suffix else 1)
        
        # Create square transparent canvas
        canvas = Image.new('RGBA', (pixel_size, pixel_size), (0, 0, 0, 0))
        
        # Resize source image to fit
        # Copy to avoid modifying original
        src_copy = img.copy()
        src_copy.thumbnail((pixel_size, pixel_size), Image.Resampling.LANCZOS)
        
        # Calculate position to center
        x = (pixel_size - src_copy.width) // 2
        y = (pixel_size - src_copy.height) // 2
        
        canvas.paste(src_copy, (x, y))
        
        filename = f'icon_{size_pt}x{size_pt}{suffix}.png'
        canvas.save(os.path.join(iconset_dir, filename))
        print(f"Generated {filename}")

    # Convert to icns
    print("Converting to icns...")
    subprocess.check_call(['iconutil', '-c', 'icns', iconset_dir])
    
    # Move to destination
    if dest_icns != 'src/artisan.icns':
         if os.path.exists(dest_icns):
             os.remove(dest_icns)
         shutil.move('src/artisan.icns', dest_icns)
    else:
         print("Icon already at destination")
    print(f"Replaced {dest_icns}")
    
    # Cleanup
    # shutil.rmtree(iconset_dir) 

if __name__ == '__main__':
    src = '/Users/arsky/.gemini/antigravity/brain/76a04239-54ed-4a79-a43b-328b75aaa9c4/uploaded_image_1_1767478630364.png'
    dest = 'src/artisan.icns'
    make_icns(src, dest)
