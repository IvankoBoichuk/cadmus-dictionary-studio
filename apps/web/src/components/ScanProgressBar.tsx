import { Progress } from "@/components/ui/progress";

import { formatNumber } from "../format";

/** BH-57: slim, viewport-pinned scan-progress bar (bar + processed/total count).
 * The scan-queue button and per-page grid now live in the control panel. */
export function ScanProgressBar({
  processed,
  total,
}: {
  processed: number;
  total: number;
}) {
  const percent = total === 0 ? 0 : Math.round((processed / total) * 100);

  return (
    <div
      className="sticky bottom-0 z-10 -mx-[clamp(1rem,4vw,2.5rem)] mt-2 grid gap-1 border-t border-border bg-background/95 px-[clamp(1rem,4vw,2.5rem)] py-2 backdrop-blur-sm"
      aria-labelledby="scan-progress-heading"
    >
      <h3 id="scan-progress-heading" className="sr-only">
        Прогрес сканування словника
      </h3>
      <p className="m-0 text-[0.85rem] font-[650] tabular-nums" role="status">
        Опрацьовано {formatNumber(processed)} / {formatNumber(total)} сторінок
      </p>
      <Progress value={percent} />
    </div>
  );
}
