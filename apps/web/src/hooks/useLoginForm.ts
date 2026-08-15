import { useFormik } from "formik";
import { useNavigate } from "react-router-dom";

import { API, apiMessageFrom } from "../api";
import { useAuth } from "../authContext";

type LoginValues = {
  email: string;
  password: string;
};

type LoginErrors = Partial<Record<keyof LoginValues, string>>;

const INITIAL_VALUES: LoginValues = { email: "", password: "" };

function validate(values: LoginValues): LoginErrors {
  const errors: LoginErrors = {};
  const email = values.email.trim();
  if (!email) {
    errors.email = "Email є обов’язковим полем.";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = "Введіть коректну email-адресу.";
  }
  if (!values.password) {
    errors.password = "Пароль є обов’язковим полем.";
  }
  return errors;
}

export function useLoginForm() {
  const navigate = useNavigate();
  const { setAuthenticated } = useAuth();
  return useFormik<LoginValues>({
    initialValues: INITIAL_VALUES,
    validate,
    validateOnBlur: true,
    validateOnChange: true,
    onSubmit: async (values, helpers) => {
      helpers.setStatus(undefined);
      try {
        const user = await API.auth.login({
          email: values.email.trim(),
          password: values.password,
        });
        setAuthenticated(user);
        navigate("/dashboard", { replace: true });
      } catch (error) {
        helpers.setStatus(
          apiMessageFrom(error) ??
            "Сервіс авторизації недоступний. Спробуйте пізніше.",
        );
      }
    },
  });
}
