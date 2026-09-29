import os
import random
import shutil

# Dataset paths
dataset = "dataset"
train_images = os.path.join(dataset, "train", "images")
train_labels = os.path.join(dataset, "train", "labels")

# New folders
valid_images = os.path.join(dataset, "valid", "images")
valid_labels = os.path.join(dataset, "valid", "labels")

test_images = os.path.join(dataset, "test", "images")
test_labels = os.path.join(dataset, "test", "labels")

# Create folders
os.makedirs(valid_images, exist_ok=True)
os.makedirs(valid_labels, exist_ok=True)
os.makedirs(test_images, exist_ok=True)
os.makedirs(test_labels, exist_ok=True)

# Get all images
images = [
    f for f in os.listdir(train_images)
    if f.lower().endswith((".jpg", ".jpeg", ".png"))
]

# Shuffle images
random.seed(42)
random.shuffle(images)

# 80% train, 10% validation, 10% test
total = len(images)

valid_count = int(total * 0.10)
test_count = int(total * 0.10)

valid_files = images[:valid_count]
test_files = images[valid_count:valid_count + test_count]

# Copy validation files
for image in valid_files:
    label = os.path.splitext(image)[0] + ".txt"

    shutil.copy2(
        os.path.join(train_images, image),
        os.path.join(valid_images, image)
    )

    shutil.copy2(
        os.path.join(train_labels, label),
        os.path.join(valid_labels, label)
    )

# Copy test files
for image in test_files:
    label = os.path.splitext(image)[0] + ".txt"

    shutil.copy2(
        os.path.join(train_images, image),
        os.path.join(test_images, image)
    )

    shutil.copy2(
        os.path.join(train_labels, label),
        os.path.join(test_labels, label)
    )

print("Dataset split completed!")
print("Total images:", total)
print("Validation images:", len(valid_files))
print("Test images:", len(test_files))
print("Training images:", total - len(valid_files) - len(test_files))