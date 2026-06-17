import sys

path1 = "frontend/src/lib/navigation.ts"
with open(path1, "r", encoding="utf-8") as f:
    content1 = f.read()

new_nav_item = """  {
    href: "/library",
    label: "Library",
    description: "View documents and versions"
  },"""

if "/library" not in content1:
    content1 = content1.replace("export const navItems: NavItem[] = [", "export const navItems: NavItem[] = [\n" + new_nav_item)

page_meta = """  if (pathname.startsWith("/library")) {
    return {
      eyebrow: "Documents",
      title: "Library",
      description: "View indexed files, extracted text versions, and document diffs."
    };
  }"""

if "/library" not in content1.split("export function getPageMeta")[1]:
    content1 = content1.replace("export function getPageMeta(pathname: string): PageMeta {", "export function getPageMeta(pathname: string): PageMeta {\n" + page_meta)

with open(path1, "w", encoding="utf-8") as f:
    f.write(content1)

path2 = "frontend/src/components/Sidebar.tsx"
with open(path2, "r", encoding="utf-8") as f:
    content2 = f.read()

icon = """  if (href === "/library") return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>;"""

if "/library" not in content2:
    content2 = content2.replace("if (href === \"/\") return", icon + "\n  if (href === \"/\") return")

with open(path2, "w", encoding="utf-8") as f:
    f.write(content2)

print("Patched nav for library successfully")
