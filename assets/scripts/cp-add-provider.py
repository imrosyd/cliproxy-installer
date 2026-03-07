import os
import sys
import json
import urllib.request

CONFIG_PATH = os.path.expanduser("~/.cli-proxy-api/config.yaml")

def print_header():
    print("=========================================")
    print("   CLIProxy - Add Custom Provider")
    print("=========================================")
    print("This will add an OpenAI-Compatible endpoint")
    print("seamlessly into your local configuration.\n")

def get_input(prompt, required=True):
    while True:
        val = input(prompt).strip()
        if val:
            return val
        if not required:
            return ""
        print("[!] This field is required.\n")

def fetch_models(base_url, api_key):
    print("\n⏳ Fetching available models from API...")
    url = base_url.rstrip("/") + "/models"
    
    try:
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            models = data.get("data", [])
            return [m.get("id") for m in models if m.get("id")]
    except Exception as e:
        print(f"❌ Failed to fetch models: {e}")
        return []

def main():
    print_header()
    
    provider_name = get_input("Provider Name (e.g., openai): ")
    base_url = get_input("Base URL (e.g., https://api.openai.com/v1): ")
    api_key = get_input("API Key (e.g., sk-...): ")
    
    models = fetch_models(base_url, api_key)
    
    if not models:
        print("\n⚠️  No models could be auto-fetched.")
        print("You can add models manually later in config.yaml.")
        models_to_add = []
    else:
        print(f"✅ Fast-fetched {len(models)} models!")
        models_to_add = models
    
    # Load existing config
    if not os.path.exists(CONFIG_PATH):
        print(f"\n❌ CLIProxy Config not found at {CONFIG_PATH}")
        print("Please run `cp-start` or reinstall CLIProxy first.")
        sys.exit(1)
        
    try:
        with open(CONFIG_PATH, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"\n❌ Error reading config.yaml: {e}")
        sys.exit(1)
        
    # Check if provider exists
    for line in lines:
        if line.strip() == f'name: "{provider_name}"' or line.strip() == f"name: {provider_name}":
            print(f"\n⚠️  Provider '{provider_name}' already exists in config.yaml.")
            print("Please edit ~/.cli-proxy-api/config.yaml manually to update it.")
            sys.exit(1)
            
    # Build YAML block manually
    yaml_block = f"""
  - name: "{provider_name}"
    base-url: "{base_url}"
    api-key-entries:
      - api-key: "{api_key}"
    models:"""
    
    for m in models_to_add:
        # Indent 6 spaces for models list items
        yaml_block += f'\n      - name: "{m}"\n        alias: "{m}"'
    
    yaml_block += "\n"

    content = "".join(lines)
    
    # Insert block
    if "openai-compatibility:" in content:
        # Replace the first occurrence of openai-compatibility: by appending to it
        content = content.replace("openai-compatibility:", "openai-compatibility:" + yaml_block, 1)
    else:
        # Otherwise append to the end of the file
        if not content.endswith("\n"):
            content += "\n"
        content += f"\nopenai-compatibility:\n{yaml_block}"
    
    # Save back
    try:
        with open(CONFIG_PATH, 'w') as f:
            f.write(content)
    except Exception as e:
        print(f"\n❌ Error saving config.yaml: {e}")
        sys.exit(1)
        
    print("\n✅ Successfully added custom provider to config.yaml!")
    print("Please restart CLIProxy using `cp-start` to apply the changes.")

if __name__ == "__main__":
    main()
