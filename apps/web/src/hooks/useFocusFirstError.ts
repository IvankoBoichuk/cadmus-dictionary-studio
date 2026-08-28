import { useEffect, type RefObject } from "react";

/**
 * After a submit attempt settles, moves focus to the first control the form
 * marked `aria-invalid="true"`, so keyboard and screen-reader users land on the
 * problem instead of having to hunt for it.
 *
 * `submitCount` is Formik's per-form counter; it changes on every submit attempt
 * (including repeated ones), which is what re-triggers the focus move.
 */
export function useFocusFirstError(
  formRef: RefObject<HTMLFormElement | null>,
  submitCount: number,
  isSubmitting: boolean,
): void {
  useEffect(() => {
    if (submitCount === 0 || isSubmitting) return;
    const invalid = formRef.current?.querySelector<HTMLElement>(
      '[aria-invalid="true"]',
    );
    invalid?.focus();
  }, [formRef, submitCount, isSubmitting]);
}
