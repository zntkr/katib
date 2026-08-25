import os
import re

tests_dir = "tests"

for filename in os.listdir(tests_dir):
    if not filename.endswith(".py"):
        continue
        
    filepath = os.path.join(tests_dir, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # AudioWorker(settings) -> AudioWorker(settings, MagicMock())
    new_content = re.sub(
        r'AudioWorker\((mock_settings|settings)\)',
        r'AudioWorker(settings=\1, audio_source=MagicMock())',
        content
    )
    
    new_content = re.sub(
        r'AudioWorker\(settings=(.*?)\)',
        r'AudioWorker(settings=\1, audio_source=MagicMock())',
        new_content
    )
    
    # We need to make sure MagicMock is imported if we inject it
    if "MagicMock" not in new_content and "MagicMock" in new_content:
        new_content = "from unittest.mock import MagicMock\n" + new_content
        
    if new_content != content:
        # Add MagicMock import safely if it wasn't there but we just added it
        if "from unittest.mock import MagicMock" not in new_content and "from unittest.mock import" not in new_content:
            new_content = "from unittest.mock import MagicMock\n" + new_content
            
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {filename}")
