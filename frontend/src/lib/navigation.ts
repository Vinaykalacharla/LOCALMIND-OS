export interface NavItem {
  href: string;
  label: string;
  description: string;
}

export interface PageMeta {
  title: string;
  description: string;
  eyebrow: string;
}

export const navItems: NavItem[] = [
  {
    href: "/library",
    label: "Library",
    description: "View documents and versions"
  },
  {
    href: "/collections",
    label: "Workspaces",
    description: "Manage persistent collections"
  },
  {
    href: "/",
    label: "Dashboard",
    description: "Overview and recent activity"
  },
  {
    href: "/upload",
    label: "Upload",
    description: "Add files to the workspace"
  },
  {
    href: "/search",
    label: "Search",
    description: "Find relevant chunks"
  },
  {
    href: "/local-chat",
    label: "Local Chat",
    description: "Offline AI chat with your documents"
  },
  {
    href: "/study",
    label: "Study Mode",
    description: "Spaced repetition & exam simulator"
  },
  {
    href: "/graph",
    label: "Graph",
    description: "View relationships"
  },
  {
    href: "/models",
    label: "Models",
    description: "Switch and validate local models"
  },
  {
    href: "/evaluate",
    label: "Evaluate",
    description: "Measure retrieval and model readiness"
  }
];

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function getPageMeta(pathname: string): PageMeta {
  if (pathname.startsWith("/library")) {
    return {
      eyebrow: "Documents",
      title: "Library",
      description: "View indexed files, extracted text versions, and document diffs."
    };
  }
  if (pathname.startsWith("/collections")) {
    return {
      eyebrow: "Organization",
      title: "Workspaces",
      description: "Group your files into persistent collections for targeted search and study."
    };
  }
  if (pathname === "/") {
    return {
      eyebrow: "Mission Control",
      title: "Your local AI workspace",
      description: "See the current state of your data, activity, and available features."
    };
  }

  if (pathname.startsWith("/upload")) {
    return {
      eyebrow: "Ingestion",
      title: "Upload and index files",
      description: "Add source material and track processing in one place."
    };
  }

  if (pathname.startsWith("/search")) {
    return {
      eyebrow: "Retrieval",
      title: "Search your local data",
      description: "Run semantic search and inspect the source text behind each result."
    };
  }

  if (pathname.startsWith("/local-chat") || pathname.startsWith("/chat")) {
    return {
      eyebrow: "Offline AI",
      title: "Secure Chat",
      description: "Chat with your documents using your local AI — fully offline, no API keys."
    };
  }

  if (pathname.startsWith("/study")) {
    return {
      eyebrow: "Learning Engine",
      title: "Study Mode",
      description: "Spaced repetition reviews and AI-generated exam simulations."
    };
  }

  if (pathname.startsWith("/graph")) {
    return {
      eyebrow: "Topology",
      title: "Explore relationships",
      description: "View how documents, topics, people, and projects connect."
    };
  }

  if (pathname.startsWith("/models")) {
    return {
      eyebrow: "Model Manager",
      title: "Control the local model stack",
      description: "Detect, switch, validate, and reindex local AI models without API keys."
    };
  }

  if (pathname.startsWith("/evaluate")) {
    return {
      eyebrow: "Evaluation",
      title: "Measure local AI quality",
      description: "Check retrieval quality, model readiness, and the current offline stack."
    };
  }

  return {
    eyebrow: "Workspace",
    title: "LocalMind OS",
    description: "Offline AI workspace"
  };
}
