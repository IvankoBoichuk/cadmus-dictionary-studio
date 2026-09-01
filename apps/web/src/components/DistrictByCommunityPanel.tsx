import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { API, apiMessageFrom, type SettlementMappingResponse } from "../api";

/**
 * Set the raion short form ("Хот.") for every mapping of one community at
 * once (BH-30). A single settlement can still be overridden afterwards in the
 * table. The community list is derived from the mappings already linked to a
 * community — no extra geography fetch.
 */
export function DistrictByCommunityPanel({
  dictionaryId,
  mappings,
  onApplied,
}: {
  dictionaryId: string;
  mappings: SettlementMappingResponse[];
  onApplied: () => void;
}) {
  const communities = useMemo(() => {
    const seen = new Map<string, string>();
    for (const m of mappings) {
      if (m.community_id && !seen.has(m.community_id)) {
        seen.set(m.community_id, m.community_name ?? m.community_id);
      }
    }
    return [...seen].map(([id, name]) => ({ id, name }));
  }, [mappings]);

  const [communityId, setCommunityId] = useState("");
  const [district, setDistrict] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (communities.length === 0) return null;

  const apply = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const { updated } = await API.settlements.setDistrictByCommunity(
        dictionaryId,
        { community_id: communityId, district: district.trim() || null },
      );
      setMessage(`Оновлено записів: ${updated}`);
      onApplied();
    } catch (err) {
      setError(
        apiMessageFrom(err) ?? "Не вдалося оновити район для громади.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="form-section">
      <h3 className="m-0 text-[0.95rem]">Район для громади</h3>
      <p className="section-hint">
        Проставити скорочення району всім населеним пунктам обраної громади.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-[0.85rem]">
          Громада
          <Select value={communityId} onValueChange={setCommunityId}>
            <SelectTrigger className="min-w-[16rem]" aria-label="Громада">
              <SelectValue placeholder="Оберіть громаду" />
            </SelectTrigger>
            <SelectContent>
              {communities.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <label className="grid gap-1 text-[0.85rem]">
          Скорочення району
          <Input
            className="w-[10rem]"
            aria-label="Скорочення району"
            value={district}
            placeholder="напр. Хот."
            onChange={(event) => setDistrict(event.target.value)}
          />
        </label>
        <Button
          type="button"
          size="sm"
          disabled={busy || !communityId}
          onClick={() => void apply()}
        >
          {busy ? "Застосовуємо…" : "Застосувати"}
        </Button>
      </div>
      {message && (
        <p className="m-0 text-[0.85rem] text-success-foreground" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
