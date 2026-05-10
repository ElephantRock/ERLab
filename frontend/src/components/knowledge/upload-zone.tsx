import { useState, useRef, useCallback } from "react";
import { Upload, FileText, AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { ingestPdf } from "@/api/knowledge";
import { toast } from "sonner";

type UploadState = "idle" | "uploading" | "success" | "error";

interface UploadZoneProps {
  onUploadSuccess?: (result: { filename: string; chunks: number }) => void;
}

export function UploadZone({ onUploadSuccess }: UploadZoneProps) {
  const [state, setState] = useState<UploadState>("idle");
  const [dragOver, setDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [uploadResult, setUploadResult] = useState<{ filename: string; chunks: number } | null>(null);
  const [fileName, setFileName] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const resetState = useCallback(() => {
    setState("idle");
    setErrorMessage("");
    setUploadResult(null);
    setFileName("");
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      // Validate file extension
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setState("error");
        setErrorMessage(`"${file.name}" is not a PDF. Only PDF files are accepted.`);
        return;
      }

      setState("uploading");
      setFileName(file.name);
      setErrorMessage("");

      try {
        const result = await ingestPdf(file);
        setState("success");
        setUploadResult({ filename: result.filename, chunks: result.chunks });
        toast.success(`Uploaded ${result.filename} (${result.chunks} chunks)`);
        onUploadSuccess?.({ filename: result.filename, chunks: result.chunks });
      } catch (err) {
        setState("error");
        const message = err instanceof Error ? err.message : "Upload failed";
        setErrorMessage(message);
        toast.error(message);
      }
    },
    [onUploadSuccess],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset input so the same file can be re-selected
      e.target.value = "";
    },
    [handleFile],
  );

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  return (
    <Card data-testid="upload-zone">
      <CardContent className="p-4">
        <div
          role="button"
          tabIndex={0}
          data-testid="drop-area"
          className={cn(
            "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary/50",
          )}
          onClick={handleClick}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") handleClick();
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={handleInputChange}
            data-testid="file-input"
          />

          {state === "idle" && (
            <div className="flex flex-col items-center gap-2">
              <Upload className="h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-medium">Drop a PDF here or click to upload</p>
              <p className="text-xs text-muted-foreground">Only PDF files are accepted</p>
            </div>
          )}

          {state === "uploading" && (
            <div className="flex flex-col items-center gap-2" data-testid="upload-loading">
              <Loader2 className="h-8 w-8 text-primary animate-spin" />
              <p className="text-sm font-medium">Uploading {fileName}…</p>
              <Progress value={undefined} className="max-w-[200px]" />
            </div>
          )}

          {state === "success" && uploadResult && (
            <div className="flex flex-col items-center gap-2" data-testid="upload-success">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
              <p className="text-sm font-medium text-green-700">
                Successfully ingested {uploadResult.filename}
              </p>
              <p className="text-xs text-muted-foreground">
                {uploadResult.chunks} chunk{uploadResult.chunks !== 1 ? "s" : ""} indexed
              </p>
              <button
                className="text-xs text-primary underline mt-1"
                onClick={(e) => {
                  e.stopPropagation();
                  resetState();
                }}
              >
                Upload another
              </button>
            </div>
          )}

          {state === "error" && (
            <div className="flex flex-col items-center gap-2" data-testid="upload-error">
              <AlertCircle className="h-8 w-8 text-destructive" />
              <p className="text-sm font-medium text-destructive">{errorMessage}</p>
              <button
                className="text-xs text-primary underline mt-1"
                onClick={(e) => {
                  e.stopPropagation();
                  resetState();
                }}
              >
                Try again
              </button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
