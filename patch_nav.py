import sys

path1 = "frontend/src/lib/navigation.ts"
with open(path1, "r", encoding="utf-8") as f:
    content1 = f.read()

new_nav_item = """  {
    href: "/collections",
    label: "Workspaces",
    description: "Manage persistent collections"
  },"""

if "/collections" not in content1:
    content1 = content1.replace("export const navItems: NavItem[] = [", "export const navItems: NavItem[] = [\n" + new_nav_item)

page_meta = """  if (pathname.startsWith("/collections")) {
    return {
      eyebrow: "Organization",
      title: "Workspaces",
      description: "Group your files into persistent collections for targeted search and study."
    };
  }"""

if "/collections" not in content1.split("export function getPageMeta")[1]:
    content1 = content1.replace("export function getPageMeta(pathname: string): PageMeta {", "export function getPageMeta(pathname: string): PageMeta {\n" + page_meta)

with open(path1, "w", encoding="utf-8") as f:
    f.write(content1)

path2 = "frontend/src/components/Sidebar.tsx"
with open(path2, "r", encoding="utf-8") as f:
    content2 = f.read()

icon = """  if (href === "/collections") return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>;"""

if "/collections" not in content2:
    content2 = content2.replace("if (href === \"/\") return", icon + "\n  if (href === \"/\") return")

with open(path2, "w", encoding="utf-8") as f:
    f.write(content2)

print("Patched nav successfully")
