with open(r"d:\OneDrive\Desktop\LOCALMIND OS\frontend\src\lib\api.ts", "r", encoding="utf-8") as f:
    lines = f.readlines()

# The error is that `askQuestion` definition was interrupted at line 424.
# We will find `export async function askQuestion` and delete everything until `export async function getGraph(): Promise<GraphResponse> {`
# except for the `session_id...` end of `askQuestion`.
# Actually it's simpler:
# Just keep lines up to 424
# Keep lines 584 onwards
new_lines = lines[:424] + lines[583:]

with open(r"d:\OneDrive\Desktop\LOCALMIND OS\frontend\src\lib\api.ts", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
