import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface ExportButtonProps {
  proposalMd: string | null;
  proposalLatex: string | null;
  title: string;
}

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportButton({ proposalMd, proposalLatex, title }: ExportButtonProps) {
  if (!proposalMd && !proposalLatex) return null;

  const safeName = title.replace(/[^a-zA-Z0-9]/g, "_").slice(0, 50);

  return (
    <div className="flex items-center gap-2">
      {proposalMd && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => download(`${safeName}.md`, proposalMd, "text/markdown")}
        >
          <Download className="mr-2 h-4 w-4" />
          Markdown
        </Button>
      )}
      {proposalLatex && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => download(`${safeName}.tex`, proposalLatex, "application/x-latex")}
        >
          <Download className="mr-2 h-4 w-4" />
          LaTeX
        </Button>
      )}
    </div>
  );
}
