export const FORMAT_OPTIONS = [
  { id: "readme", label: "README.md", color: "brand", ext: ".md" },
  { id: "jsdoc", label: "JSDoc", color: "warning", ext: ".js" },
  { id: "openapi", label: "OpenAPI YAML", color: "success", ext: ".yaml" },
  { id: "confluence", label: "Confluence", color: "info", ext: ".html" },
  { id: "docusaurus", label: "Docusaurus MDX", color: "teal", ext: ".mdx" },
] as const;

export type FormatId = (typeof FORMAT_OPTIONS)[number]["id"];
