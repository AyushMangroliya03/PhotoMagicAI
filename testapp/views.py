import requests
from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import HttpResponse, Http404
import os
import mimetypes

def save_generated_images(user_id, images):
    save_path = os.path.join('media', 'generated', user_id)
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    generated_images = []
    for image in images:
        image_name = image['name']
        image_content = image['content']
        with open(os.path.join(save_path, image_name), 'wb') as f:
            f.write(image_content)
        generated_images.append(os.path.join(save_path, image_name))
    return generated_images

def run_command(user_id, images):
    files = [('images', (image.name, image.read(), image.content_type)) for image in images]
    response = requests.post('http://<GPU_MACHINE_IP>:5000/run_command', data={'user_id': user_id}, files=files)
    if response.status_code == 200 and response.json()['status'] == 'success':
        return response.json()['generated_images']
    return []

def upload_view(request):
    context = {}
    if request.method == 'POST':
        username = request.POST.get('name')
        images = request.FILES.getlist('upload')

        if len(images) < 5:
            context['error'] = "Please upload at least 5 images."
            return render(request, 'home.html', context)

        upload_time = timezone.now().strftime("%Y%m%d%H%M%S")
        user_id = f"{username}_{upload_time}"

        context['success'] = "Your images are successfully uploaded."
        context['message'] = "Please wait for 20-30 min to get your personalized images."

        generated_images_info = run_command(user_id, images)
        if generated_images_info:
            generated_images = save_generated_images(user_id, generated_images_info)
            request.session['generated_images'] = [os.path.basename(img) for img in generated_images]
            request.session['user_id'] = user_id  # Store user_id in session
            return redirect('generated_images', user_id=user_id)
        else:
            context['error'] = "An error occurred during processing."
            return render(request, 'home.html', context)

    return render(request, 'home.html', context)

def generated_images(request, user_id):
    generated_images = request.session.get('generated_images', [])
    user_id = request.session.get('user_id')  # Retrieve user_id from session

    return render(request, 'generated_images.html', {
        'generated_images': generated_images,
        'user_id': user_id  # Pass user_id to the template
    })

def download_image(request, user_id, image_name):
    image_path = os.path.join('media', 'generated', user_id, image_name)

    if os.path.exists(image_path):
        with open(image_path, 'rb') as file:
            mime_type, _ = mimetypes.guess_type(image_path)
            response = HttpResponse(file, content_type=mime_type)
            response['Content-Disposition'] = f'attachment; filename={image_name}'
            return response
    else:
        raise Http404("Image does not exist")
