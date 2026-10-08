import os
import subprocess
import sys
from huggingface_hub import hf_hub_download

REPO_ID = "litert-community/gemma-4-E2B-it-litert-lm"
FILENAME = "gemma-4-E2B-it.litertlm"
DEST_DIR = os.path.join(os.path.dirname(__file__), "models")

def get_token():
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.startswith("HF_TOKEN="):
                    return line.strip().split("=", 1)[1]
    return None

def main():
    token = get_token()
    os.makedirs(DEST_DIR, exist_ok=True)
    target_path = os.path.join(DEST_DIR, FILENAME)

    if os.path.exists(target_path) and os.path.getsize(target_path) > 2_000_000_000:
        print(f"Model already downloaded at: {target_path}")
    else:
        print(f"Starting download of {FILENAME} (~2.58 GB) from {REPO_ID}...")
        downloaded = hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            token=token,
            local_dir=DEST_DIR,
            local_dir_use_symlinks=False
        )
        print(f"Download complete: {downloaded}")

    print("\nPushing model to connected Android device via ADB...")
    # Target 1: App-specific external storage (SELinux never blocks app from reading this!)
    app_models_dir = "/sdcard/Android/data/com.teja.gemmmobile/files/models"
    subprocess.run(["adb", "shell", "mkdir", "-p", app_models_dir])
    res = subprocess.run(["adb", "push", target_path, f"{app_models_dir}/{FILENAME}"])
    
    # Target 2: /sdcard/Download
    if res.returncode != 0:
        print("Push to app dir failed, pushing to /sdcard/Download/...")
        res = subprocess.run(["adb", "push", target_path, f"/sdcard/Download/{FILENAME}"])

    if res.returncode == 0:
        print(f"\nSUCCESS! Model pushed to device.")
        print("Now open GemmaMobile on your phone — it will detect the model and initialize GPU automatically!")
    else:
        print(f"\nADB push failed with returncode {res.returncode}")

if __name__ == "__main__":
    main()
