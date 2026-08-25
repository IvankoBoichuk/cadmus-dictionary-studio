import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type MemberResponse,
  type Role,
} from "../api";

export type MembersLoadState =
  | { status: "loading" }
  | { status: "loaded"; members: MemberResponse[]; myRole: Role }
  | { status: "error"; message: string };

export type MemberActionState = { pending: boolean; error: string | undefined };

/** BH-170: loads a project's members and offers invite/re-role/remove actions. */
export function useDictionaryMembers(dictionaryId: string) {
  const [state, setState] = useState<MembersLoadState>({ status: "loading" });
  const [actionState, setActionState] = useState<
    Record<string, MemberActionState | undefined>
  >({});

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ status: "loading" });
      API.members.list(dictionaryId, { signal }).then(
        (response) =>
          setState({
            status: "loaded",
            members: response.members,
            myRole: response.my_role,
          }),
        (error: unknown) => {
          if (isAbortError(error)) return;
          setState({
            status: "error",
            message:
              apiMessageFrom(error) ??
              "Не вдалося завантажити учасників проєкту. Спробуйте пізніше.",
          });
        },
      );
    },
    [dictionaryId],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const add = useCallback(
    async (email: string, role: Role): Promise<boolean> => {
      setActionState((current) => ({
        ...current,
        add: { pending: true, error: undefined },
      }));
      try {
        const member = await API.members.add(dictionaryId, { email, role });
        setState((current) =>
          current.status === "loaded"
            ? { ...current, members: [...current.members, member] }
            : current,
        );
        setActionState((current) => ({ ...current, add: undefined }));
        return true;
      } catch (error) {
        setActionState((current) => ({
          ...current,
          add: {
            pending: false,
            error:
              apiMessageFrom(error) ??
              "Не вдалося запросити учасника. Перевірте пошту та роль.",
          },
        }));
        return false;
      }
    },
    [dictionaryId],
  );

  const changeRole = useCallback(
    async (userId: string, role: Role): Promise<void> => {
      setActionState((current) => ({
        ...current,
        [userId]: { pending: true, error: undefined },
      }));
      try {
        const updated = await API.members.changeRole(dictionaryId, userId, { role });
        setState((current) =>
          current.status === "loaded"
            ? {
                ...current,
                members: current.members.map((member) =>
                  member.user_id === userId ? updated : member,
                ),
              }
            : current,
        );
        setActionState((current) => ({ ...current, [userId]: undefined }));
      } catch (error) {
        setActionState((current) => ({
          ...current,
          [userId]: {
            pending: false,
            error:
              apiMessageFrom(error) ??
              "Не вдалося змінити роль учасника. Спробуйте пізніше.",
          },
        }));
      }
    },
    [dictionaryId],
  );

  const remove = useCallback(
    async (userId: string): Promise<void> => {
      setActionState((current) => ({
        ...current,
        [userId]: { pending: true, error: undefined },
      }));
      try {
        await API.members.remove(dictionaryId, userId);
        setState((current) =>
          current.status === "loaded"
            ? {
                ...current,
                members: current.members.filter((member) => member.user_id !== userId),
              }
            : current,
        );
        setActionState((current) => {
          const rest = { ...current };
          delete rest[userId];
          return rest;
        });
      } catch (error) {
        setActionState((current) => ({
          ...current,
          [userId]: {
            pending: false,
            error:
              apiMessageFrom(error) ??
              "Не вдалося видалити учасника. Спробуйте пізніше.",
          },
        }));
      }
    },
    [dictionaryId],
  );

  return { state, actionState, add, changeRole, remove, reload: () => load() } as const;
}
