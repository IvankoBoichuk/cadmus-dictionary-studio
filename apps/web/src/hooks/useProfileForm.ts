import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { API, apiMessageFrom, fieldErrorsFrom } from "../api";
import { useAuth } from "../authContext";

const MAX_NAME_LENGTH = 200;

const profileSchema = z.object({
  name: z
    .string()
    .trim()
    .max(MAX_NAME_LENGTH, `Не більше ${MAX_NAME_LENGTH} символів.`),
});

export type ProfileValues = z.infer<typeof profileSchema>;

export function useProfileForm() {
  const { session, setAuthenticated } = useAuth();
  const currentName =
    session.status === "authenticated" ? (session.user.name ?? "") : "";
  const [saved, setSaved] = useState(false);

  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: currentName },
    mode: "onTouched",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    setSaved(false);
    try {
      const user = await API.auth.updateProfile({
        name: values.name.trim() === "" ? null : values.name.trim(),
      });
      setAuthenticated(user);
      form.reset({ name: user.name ?? "" });
      setSaved(true);
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors?.name) {
        form.setError("name", { message: apiErrors.name });
        return;
      }
      form.setError("root", {
        message:
          apiMessageFrom(error) ??
          "Не вдалося зберегти ім’я. Спробуйте пізніше.",
      });
    }
  });

  return { form, onSubmit, saved };
}
