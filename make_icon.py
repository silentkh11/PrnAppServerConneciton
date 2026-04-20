from PIL import Image
import os


def create_hd_icon(input_png, output_ico):
    print(f"Processing {input_png} for HD Icon...")

    try:
        # 1. Open the source image
        img = Image.open(input_png).convert("RGBA")
        width, height = img.size

        # 2. Make the perfect square canvas
        max_dim = max(width, height, 256)
        square_canvas = Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))

        # 3. Center the image
        left = (max_dim - width) // 2
        top = (max_dim - height) // 2
        square_canvas.paste(img, (left, top), img)

        # 4. THE SECRET SAUCE: Manually generate ultra-smooth frames for every Windows size
        icon_sizes = [256, 128, 64, 48, 32, 16]
        hd_frames = []

        for size in icon_sizes:
            # LANCZOS applies professional anti-aliasing so edges stay crisp and smooth
            frame = square_canvas.resize((size, size), Image.Resampling.LANCZOS)
            hd_frames.append(frame)

        # 5. Package them all into one mega-file
        # We save the 256x256 first, then append all the smaller HD versions inside it
        hd_frames[0].save(
            output_ico,
            format='ICO',
            sizes=[(s, s) for s in icon_sizes],
            append_images=hd_frames[1:]
        )

        print(f"Success! HD Icon created: {output_ico}")

    except FileNotFoundError:
        print(f"ERROR: Could not find '{input_png}'")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Make sure your background-removed image is named exactly this:
    input_file = "TheImg.png"
    output_file = "icon.ico"

    create_hd_icon(input_file, output_file)