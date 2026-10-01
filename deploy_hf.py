#!/usr/bin/env python3
"""
Deploy Fine-Tuned Gemma 4 E2B Server to Hugging Face Spaces (1-Click Automated Script)
"""
import os
import sys
import getpass
from dotenv import load_dotenv
from huggingface_hub import HfApi, login

# Load .env
load_dotenv(override=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def main():
    print("=" * 60)
    print("🚀 TejaAI - 1-Click Hugging Face Space Deployment")
    print("=" * 60)
    
    # 1. Check for token
    token = os.environ.get("HF_TOKEN")
    if token:
        print(f"🔑 Found HF_TOKEN in .env ({token[:8]}...)")
    elif len(sys.argv) > 1 and sys.argv[1].startswith("hf_"):
        token = sys.argv[1]

    if not token:
        print("\n🔑 Please enter your Hugging Face Access Token.")
        print("👉 You can create a WRITE token here: https://huggingface.co/settings/tokens")
        token = input("\nEnter HF Token (hf_...): ").strip()

    if not token:
        print("❌ Error: No token provided. Exiting.")
        sys.exit(1)

    api = HfApi(token=token)
    try:
        user_info = api.whoami(token=token)
        username = user_info["name"]
        print(f"\n✅ Authenticated as Hugging Face user: @{username}")
    except Exception as e:
        print(f"\n❌ Invalid Hugging Face Token: {e}")
        print("Please ensure your token is valid and has WRITE permissions.")
        sys.exit(1)

    # 2. Space Name
    default_space_name = "teja-ai-gemma4-server"
    if len(sys.argv) > 2 and sys.argv[2].strip():
        space_name = sys.argv[2].strip()
    else:
        try:
            space_name = input(f"\nEnter Space Name [{default_space_name}]: ").strip() or default_space_name
        except (EOFError, KeyboardInterrupt):
            space_name = default_space_name
    space_id = f"{username}/{space_name}"

    print(f"\n📦 Target Space: https://huggingface.co/spaces/{space_id}")

    # 3. Create Space if not exists
    print("\n🛠️ Creating Hugging Face Space (SDK: Gradio, Free Tier)...")
    try:
        api.create_repo(
            repo_id=space_id,
            repo_type="space",
            space_sdk="gradio",
            exist_ok=True,
            token=token,
        )
        print("✅ Space repository ready.")
    except Exception as e:
        print(f"⚠️ Note on space creation: {e}")

    # 4. Set HF_TOKEN secret inside the Space so it can download google/gemma-4-E2B
    print("\n🔐 Configuring HF_TOKEN secret inside Space for gated model access...")
    try:
        api.add_space_secret(
            repo_id=space_id,
            key="HF_TOKEN",
            value=token,
            token=token,
        )
        print("✅ HF_TOKEN secret set in Space.")
    except Exception as e:
        print(f"⚠️ Warning: Could not set space secret automatically ({e}).")
        print(f"   You can manually add HF_TOKEN in: https://huggingface.co/spaces/{space_id}/settings")

    # 5. Upload files
    source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hf_space")
    if not os.path.exists(source_dir):
        print(f"❌ Error: Directory '{source_dir}' not found!")
        sys.exit(1)

    print(f"\n⬆️ Uploading model adapter, FastAPI server & Gradio UI to Hugging Face...")
    print("   This might take 1-2 minutes depending on your internet connection (approx. 35MB)...")
    try:
        api.upload_folder(
            folder_path=source_dir,
            repo_id=space_id,
            repo_type="space",
            token=token,
            commit_message="Deploy TejaAI Gemma 4 Server with adapter weights",
        )
        print("✅ Upload completed successfully!")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        sys.exit(1)

    # 6. Format endpoints
    # Hugging Face space endpoint subdomain is: {username}-{space_name}.hf.space (dots and underscores replaced by dashes)
    subdomain = f"{username}-{space_name}".lower().replace("_", "-").replace(".", "-")
    api_url = f"https://{subdomain}.hf.space/v1"

    print("\n" + "=" * 60)
    print("🎉 DEPLOYMENT COMPLETE!")
    print("=" * 60)
    print(f"🌐 Web UI:   https://huggingface.co/spaces/{space_id}")
    print(f"⚡ API URL:  {api_url}")
    print("=" * 60)
    print("\n⏳ Hugging Face is now building and starting your container (takes 2-3 mins).")
    print("   Open the Web UI link above to watch the build log!")
    print(f"\n💡 When the status shows 'Running', your API endpoint is ready at:\n   {api_url}")

    # 7. Update .env
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Update or add TEJA_MODEL_URL
            import re
            if re.search(r"^TEJA_MODEL_URL=.*$", content, flags=re.MULTILINE):
                content = re.sub(r"^TEJA_MODEL_URL=.*$", f"TEJA_MODEL_URL={api_url}", content, flags=re.MULTILINE)
            else:
                content += f"\nTEJA_MODEL_URL={api_url}\n"

            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"\n✅ Automatically updated TEJA_MODEL_URL in your local .env file!")
        except Exception as e:
            print(f"Note: Could not update .env: {e}")

if __name__ == "__main__":
    main()
