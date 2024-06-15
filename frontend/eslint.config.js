import path from "node:path";
import { fileURLToPath } from "node:url";

import js from "@eslint/js";
import prettierConfig from "eslint-config-prettier";
import ts from "typescript-eslint";
import vueParser from "vue-eslint-parser";
import { FlatCompat } from "@eslint/eslintrc";

const eslintrc = new FlatCompat({
  baseDirectory: path.dirname(fileURLToPath(import.meta.url)),
});

export default ts.config(
  {
    ignores: ["dist/"],
  },
  js.configs.recommended,
  ...ts.configs.recommended, // recommendedTypeChecked doesn't do as well as tsc
  ...eslintrc.extends("plugin:vue/vue3-recommended"), // Depends on eslint-plugin-vue
  prettierConfig,
  {
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: ts.parser,
        EXPERIMENTAL_useProjectService: true,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
  },
);
