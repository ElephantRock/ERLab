import { useState } from "react";
import { exportPdf, bulkExport } from "@/api/exports";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface ExportDialogProps {
  /** Single idea export — pass idea_id */
  ideaId?: number;
  /** Bulk export — pass array of idea_ids */
  ideaIds?: number[];
  title?: string;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportDialog({ ideaId, ideaIds, title }: ExportDialogProps) {
  const [format, setFormat] = useState<"pdf" | "markdown">("pdf");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const isBulk = !!ideaIds && ideaIds.length > 0;

  async function handleExport() {
    setLoading(true);
    try {
      if (isBulk) {
        const blob = await bulkExport({ idea_ids: ideaIds!, format });
        const timestamp = new Date().toISOString().slice(0, 10);
        downloadBlob(blob, `ideas_export_${timestamp}.zip`);
        toast.success(`Exported ${ideaIds!.length} idea(s) as ${format.toUpperCase()}`);
      } else if (ideaId) {
        const blob = await exportPdf({ idea_id: ideaId });
        const safeTitle = (title || "idea").replace(/[^a-zA-Z0-9]/g, "_").slice(0, 50);
        downloadBlob(blob, `${safeTitle}.${format === "pdf" ? "pdf" : "html"}`);
        toast.success("PDF exported");
      }
      setOpen(false);
    } catch (err) {
      toast.error("Export failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" data-testid="export-dialog-trigger">
          <Download className="mr-2 h-4 w-4" />
          {isBulk ? `Export ${ideaIds!.length} Ideas` : "Export"}
        </Button>
      </DialogTrigger>
      <DialogContent data-testid="export-dialog">
        <DialogHeader>
          <DialogTitle>
            {isBulk ? "Bulk Export Ideas" : "Export Idea"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium mb-1 block">Format</label>
            <Select
              value={format}
              onValueChange={(v) => setFormat(v as "pdf" | "markdown")}
            >
              <SelectTrigger data-testid="export-format-select" aria-label="Export format">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pdf">PDF</SelectItem>
                <SelectItem value="markdown">Markdown (ZIP)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {isBulk && (
            <p className="text-sm text-muted-foreground">
              {ideaIds!.length} idea(s) will be exported as a ZIP archive.
            </p>
          )}
          <Button
            onClick={handleExport}
            disabled={loading}
            data-testid="export-submit-btn"
            className="w-full"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Export {format === "pdf" ? "PDF" : "Markdown ZIP"}
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
