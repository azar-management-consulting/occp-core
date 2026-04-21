/**
 * Sample tool: echo
 *
 * Tools are pure functions that take structured input and return structured
 * output. OCCP wraps each call in the Verified Autonomy Pipeline before
 * the agent sees the result.
 */
export const echoTool = {
  name: "echo",
  description: "Return the input unchanged. Useful for smoke tests.",
  parameters: {
    type: "object",
    properties: {
      message: { type: "string", description: "text to echo back" },
    },
    required: ["message"],
  },
  async run({ message }) {
    return { echoed: message, ts: new Date().toISOString() };
  },
};
