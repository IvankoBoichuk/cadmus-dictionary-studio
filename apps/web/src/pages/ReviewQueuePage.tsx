import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import type { ReviewQueueItemResponse } from "../api";
import { formatDate } from "../format";
import { useReviewDecision } from "../hooks/useReviewDecision";
import { useReviewQueue } from "../hooks/useReviewQueue";

const COMPACT =
  "text-[0.85rem] [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_td]:align-middle";

type Group = {
  dictionaryId: string;
  title: string;
  items: ReviewQueueItemResponse[];
};

function groupByDictionary(items: ReviewQueueItemResponse[]): Group[] {
  const order: string[] = [];
  const groups = new Map<string, Group>();
  for (const item of items) {
    let group = groups.get(item.dictionary_id);
    if (!group) {
      group = {
        dictionaryId: item.dictionary_id,
        title: item.dictionary_title ?? "Без назви",
        items: [],
      };
      groups.set(item.dictionary_id, group);
      order.push(item.dictionary_id);
    }
    group.items.push(item);
  }
  return order.map((id) => groups.get(id)!);
}

function SendBackButton({
  disabled,
  onConfirm,
}: {
  disabled: boolean;
  onConfirm: (note: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setNote("");
      }}
    >
      <PopoverTrigger asChild>
        <Button type="button" size="sm" variant="secondary" disabled={disabled}>
          Повернути
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="grid gap-2">
          <label className="grid gap-1 text-[0.82rem]">
            <span>Причина повернення (необовʼязково)</span>
            <Textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              placeholder="Що потрібно доопрацювати?"
            />
          </label>
          <Button
            type="button"
            size="sm"
            disabled={disabled}
            onClick={() => {
              onConfirm(note);
              setOpen(false);
              setNote("");
            }}
          >
            Повернути на доопрацювання
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function QueueTable({
  group,
  onDecision,
}: {
  group: Group;
  onDecision: ReturnType<typeof useReviewDecision>;
}) {
  const { state, approve, sendBack } = onDecision;

  return (
    <section className="grid gap-2">
      <h3 className="m-0 text-[1rem]">{group.title}</h3>
      <Table className={cn(COMPACT, "max-w-3xl")}>
        <caption className="sr-only">
          Статті словника «{group.title}», що очікують перевірки
        </caption>
        <TableHeader>
          <TableRow>
            <TableHead scope="col">Заголовне слово</TableHead>
            <TableHead scope="col" className="text-right">
              Полів
            </TableHead>
            <TableHead scope="col">Оновлено</TableHead>
            <TableHead scope="col">Дії</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {group.items.map((item) => {
            const busy =
              state.status === "pending" && state.entryId === item.entry_id;
            const error =
              state.status === "error" && state.entryId === item.entry_id
                ? state.message
                : null;
            return (
              <TableRow key={item.entry_id}>
                <TableCell className="font-[650] [overflow-wrap:anywhere]">
                  <Link to={`/entries/${item.entry_id}`} className="text-primary">
                    {item.headword}
                  </Link>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {item.field_count}
                </TableCell>
                <TableCell className="text-muted-foreground tabular-nums">
                  {formatDate(item.updated_at)}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Button
                      type="button"
                      size="sm"
                      disabled={busy}
                      onClick={() => approve(item.entry_id)}
                    >
                      Схвалити
                    </Button>
                    <SendBackButton
                      disabled={busy}
                      onConfirm={(note) => sendBack(item.entry_id, note)}
                    />
                  </div>
                  {error && (
                    <p className="form-error mt-1 text-[0.8rem]" role="alert">
                      {error}
                    </p>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </section>
  );
}

export function ReviewQueuePage() {
  const { state, reload } = useReviewQueue();
  const decision = useReviewDecision(reload);

  const groups = useMemo(
    () => (state.status === "loaded" ? groupByDictionary(state.items) : []),
    [state],
  );

  const total = state.status === "loaded" ? state.items.length : 0;

  return (
    <>
      <div className="mb-2 min-w-0">
        <h2 className="mb-2 text-[1.15rem]">Черга рецензування</h2>
        <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
          Статті зі станом «Очікує перевірки» з усіх словників, де ви —
          рецензент або власник. Схваліть статтю, щоб завершити її, або
          поверніть редакторові на доопрацювання.
        </p>
      </div>

      <div className="dictionary-form">
        {state.status === "loading" && (
          <p role="status">Завантажуємо чергу…</p>
        )}
        {state.status === "error" && (
          <p className="form-error" role="alert">
            {state.message}
          </p>
        )}
        {state.status === "loaded" && total === 0 && (
          <p className="lede">Немає статей, що очікують перевірки.</p>
        )}
        {state.status === "loaded" && total > 0 && (
          <div className="grid gap-5">
            <p className="m-0 text-[0.82rem] text-muted-foreground tabular-nums">
              {total} статей у {groups.length} словниках
            </p>
            {groups.map((group) => (
              <QueueTable
                key={group.dictionaryId}
                group={group}
                onDecision={decision}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
