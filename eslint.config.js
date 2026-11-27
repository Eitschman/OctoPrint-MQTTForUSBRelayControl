export default [
  {
    files: ["octoprint_mqttforusbrelaycontrol/static/js/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: { window: "readonly", globalThis: "readonly" },
    },
    rules: { "no-unused-vars": "error", "no-undef": "error", eqeqeq: "error" },
  },
];
