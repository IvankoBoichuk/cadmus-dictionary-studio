import { RefreshCw, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

import {
  apiMessageFrom,
  type ProcessingTaskResponse,
  type ProcessingTaskStatus,
} from "../api";
import { formatDate } from "../format";
import { useProcessingTasks } from "../hooks/useProcessingTasks";
import {
  formatTaskDuration,
  PROCESSING_TASK_KIND_LABELS,
  PROCESSING_TASK_STATUS_LABELS,
  PROCESSING_TASK_STATUS_VARIANT,
} from "../processingTaskLabels";

const COMPACT =
  "text-[0.85rem] [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_td]:align-top";

type Filter = ProcessingTaskStatus | "all";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "Усі" },
  { value: "running", label: PROCESSING_TASK_STATUS_LABELS.running },
  { value: "queued", label: PROCESSING_TASK_STATUS_LABELS.queued },
  { value: "failed", label: PROCESSING_TASK_STATUS_LABELS.failed },
  { value: "succeeded", label: PROCESSING_TASK_STATUS_LABELS.succeeded },
];

function TaskRow({
  task,
  retrying,
  onRetry,
}: {
  task: ProcessingTaskResponse;
  retrying: boolean;
  onRetry: (task: ProcessingTaskResponse) => void;
}) {
  const duration = formatTaskDuration(task.started_at, task.finished_at);
  return (
    <>
      <TableRow>
        <TableCell className="font-[650]">
          {PROCESSING_TASK_KIND_LABELS[task.kind]}
        </TableCell>
        <TableCell className="[overflow-wrap:anywhere]">
          {task.target_label ?? "—"}
        </TableCell>
        <TableCell>
          <Badge variant={PROCESSING_TASK_STATUS_VARIANT[task.status]}>
            {PROCESSING_TASK_STATUS_LABELS[task.status]}
          </Badge>
        </TableCell>
        <TableCell className="tabular-nums text-muted-foreground">
          {duration ?? "—"}
        </TableCell>
        <TableCell className="tabular-nums text-muted-foreground">
          {formatDate(task.created_at)}
        </TableCell>
        <TableCell>
          {task.status === "failed" && (
            <Button
              size="sm"
              variant="secondary"
              type="button"
              disabled={retrying}
              onClick={() => onRetry(task)}
            >
              <RotateCcw aria-hidden="true" />
              {retrying ? "Перезапуск…" : "Перезапустити"}
            </Button>
          )}
        </TableCell>
      </TableRow>
      {task.error && (
        <TableRow>
          <TableCell colSpan={6} className="pt-0">
            <details className="text-[0.8rem]">
              <summary className="cursor-pointer text-danger-soft-foreground">
                Деталі помилки
              </summary>
              <pre className="mt-1 max-h-40 overflow-auto rounded-md bg-accent/40 p-2 font-mono text-[0.75rem] whitespace-pre-wrap [overflow-wrap:anywhere]">
                {task.error}
              </pre>
            </details>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function TasksWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const { state, retry, retryingId, refresh } = useProcessingTasks(dictionaryId);
  const [filter, setFilter] = useState<Filter>("all");
  const [retryError, setRetryError] = useState<string | null>(null);

  const tasks = useMemo(
    () => (state.status === "loaded" ? state.tasks : []),
    [state],
  );
  const visible = useMemo(
    () => (filter === "all" ? tasks : tasks.filter((t) => t.status === filter)),
    [tasks, filter],
  );
  const counts = useMemo(() => {
    const map = new Map<ProcessingTaskStatus, number>();
    for (const task of tasks) {
      map.set(task.status, (map.get(task.status) ?? 0) + 1);
    }
    return map;
  }, [tasks]);

  const handleRetry = async (task: ProcessingTaskResponse) => {
    setRetryError(null);
    try {
      await retry(task.id);
    } catch (error) {
      setRetryError(
        apiMessageFrom(error) ?? "Не вдалося перезапустити задачу.",
      );
    }
  };

  return (
    <>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="mb-1 text-[1.15rem]">Задачі обробки</h2>
          <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
            OCR-скан, розбір статей і генерація схеми виконуються у фоні. Тут
            видно, що зараз працює, що завершилося помилкою, і можна перезапустити
            невдалу задачу.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          type="button"
          onClick={() => void refresh()}
        >
          <RefreshCw aria-hidden="true" />
          Оновити
        </Button>
      </div>

      <div className="dictionary-form">
        {state.status === "loading" && (
          <p role="status">Завантажуємо список задач…</p>
        )}
        {state.status === "error" && (
          <p className="form-error" role="alert">
            {state.message}
          </p>
        )}
        {state.status === "loaded" && (
          <div className="form-section">
            <div className="mb-2 flex flex-wrap gap-1">
              {FILTERS.map((option) => {
                const count =
                  option.value === "all"
                    ? tasks.length
                    : (counts.get(option.value) ?? 0);
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setFilter(option.value)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-[0.8rem] font-[650]",
                      filter === option.value
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {option.label}
                    <span className="ml-1 tabular-nums opacity-70">{count}</span>
                  </button>
                );
              })}
            </div>

            {retryError && (
              <p className="form-error" role="alert">
                {retryError}
              </p>
            )}

            {tasks.length === 0 ? (
              <p className="lede">
                Фонових задач для цього словника ще не було.
              </p>
            ) : visible.length === 0 ? (
              <p className="lede">За цим фільтром задач немає.</p>
            ) : (
              <Table className={COMPACT}>
                <caption className="sr-only">Фонові задачі словника</caption>
                <TableHeader>
                  <TableRow>
                    <TableHead scope="col">Тип</TableHead>
                    <TableHead scope="col">Ціль</TableHead>
                    <TableHead scope="col">Статус</TableHead>
                    <TableHead scope="col">Тривалість</TableHead>
                    <TableHead scope="col">Створено</TableHead>
                    <TableHead scope="col">Дії</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visible.map((task) => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      retrying={retryingId === task.id}
                      onRetry={(item) => void handleRetry(item)}
                    />
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        )}
      </div>
    </>
  );
}

export function DictionaryTasksPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return <TasksWorkspace dictionaryId={dictionaryId} />;
}
