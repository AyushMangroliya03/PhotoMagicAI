from flask import Flask, request, jsonify
import subprocess
import os
from io import BytesIO
import requests
from diffusers import DiffusionPipeline, AutoencoderKL
import torch

app = Flask(__name__)

@app.route('/run_command', methods=['POST'])
def run_command():
    user_id = request.form['user_id']
    images = request.files.getlist('images')

    image_path = f'media/{user_id}/'
    if not os.path.exists(image_path):
        os.makedirs(image_path)

    for image in images:
        image.save(os.path.join(image_path, image.filename))

    command = [
        'autotrain', 'dreambooth', '--train',
        '--model', 'stabilityai/stable-diffusion-xl-base-1.0',
        '--project-name', user_id,
        '--image-path', image_path,
        '--prompt', f"A photo of {user_id} wearing casual clothes and smiling.",
        '--resolution', '1024',
        '--batch-size', '1',
        '--num-steps', '1',
        '--gradient-accumulation', '4',
        '--lr', '1e-4',
        '--mixed-precision', 'fp16'
    ]

    try:
        subprocess.run(command, check=True)
        generated_images = run_post_training_code(user_id)
        return jsonify({'status': 'success', 'generated_images': generated_images})
    except subprocess.CalledProcessError as e:
        return jsonify({'status': 'failed', 'error': str(e)})

def run_post_training_code(user_id):
    vae = AutoencoderKL.from_pretrained(
        "madebyollin/sdxl-vae-fp16-fix",
        torch_dtype=torch.float16
    )
    pipe = DiffusionPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        vae=vae,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True
    )
    pipe.to("cuda")
    pipe.load_lora_weights(f"{user_id}", weight_name="pytorch_lora_weights.safetensors")

    prompt = f"A portrait of {user_id} wearing a professional business suit in an professional office"
    images = pipe(prompt=prompt, num_inference_steps=25, num_images_per_prompt=3)

    generated_images = save_generated_images(images, user_id)
    del vae
    del pipe
    torch.cuda.empty_cache()

    return generated_images

def save_generated_images(images, user_id):
    generated_images = []
    for i, img in enumerate(images['images']):
        img_io = BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        generated_images.append({
            'name': f'generated_{i}.png',
            'content': img_io.read()
        })

    return generated_images

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
