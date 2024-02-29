import path from "node:path";
import { fileURLToPath } from "node:url";

import js from "@eslint/js";
import ts from "typescript-eslint";
import vueParser from "vue-eslint-parser";
import { FlatCompat } from "@eslint/eslintrc";

const eslintrc = new FlatCompat({
  baseDirectory: path.dirname(fileURLToPath(import.meta.url)),
});

export default ts.config(
  js.configs.recommended,
  ...ts.configs.recommendedTypeChecked,
  ...eslintrc.extends("plugin:vue/vue3-recommended"), // Depends on `eslint-plugin-vue`
  {
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: ts.parser,
        EXPERIMENTAL_useProjectService: true,
      },
    },
  },
);
