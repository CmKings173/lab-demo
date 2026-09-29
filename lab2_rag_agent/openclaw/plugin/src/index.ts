import { Type } from "typebox";
import { defineToolPlugin } from "openclaw/plugin-sdk/tool-plugin";

export const TOOL_NAMES = [
  "search_products",
  "get_product",
  "search_product_documents",
  "compare_products",
  "compare_configurations",
  "estimate_ai_requirements",
] as const;

export type ToolName = (typeof TOOL_NAMES)[number];

type ToolApiConfig = { toolApiBaseUrl: string };

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

const closedObject = { additionalProperties: false } as const;

const nullableInteger = (minimum = 0) =>
  Type.Optional(Type.Union([Type.Integer({ minimum }), Type.Null()]));
const nullableNumber = (minimum = 0) =>
  Type.Optional(Type.Union([Type.Number({ minimum }), Type.Null()]));
const nullableString = () => Type.Optional(Type.Union([Type.String(), Type.Null()]));

const productFilterSchema = Type.Object(
  {
    min_ram_gb: nullableInteger(),
    min_gpu_count: nullableInteger(),
    max_base_price_vnd: nullableInteger(),
    max_listed_price_vnd: nullableInteger(),
    product_type: Type.Optional(
      Type.Union([
        Type.Literal("ai_server"),
        Type.Literal("ai_workstation"),
        Type.Literal("ai_pc"),
        Type.Null(),
      ]),
    ),
    min_total_gpu_vram_gb: nullableNumber(),
    min_installed_ram_gb: nullableInteger(),
    gpu_vendor: nullableString(),
    availability: nullableString(),
  },
  closedObject,
);

export const toolApiConfigSchema = Type.Object(
  {
    toolApiBaseUrl: Type.String({
      format: "uri",
      description: "Base URL of the private Lab 2 tool API, for example http://127.0.0.1:8090.",
    }),
  },
  closedObject,
);

const searchProductsSchema = Type.Object(
  {
    filters: Type.Optional(productFilterSchema),
    query: nullableString(),
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100 })),
  },
  closedObject,
);

const getProductSchema = Type.Object(
  { product_id: Type.String({ minLength: 1 }) },
  closedObject,
);

const searchDocumentsSchema = Type.Object(
  {
    query: Type.String({ minLength: 1 }),
    product_id: nullableString(),
    top_k: Type.Optional(Type.Integer({ minimum: 1, maximum: 50 })),
  },
  closedObject,
);

const compareProductsSchema = Type.Object(
  { product_ids: Type.Array(Type.String(), { minItems: 2 }) },
  closedObject,
);

const compareConfigurationsSchema = Type.Object(
  {
    configuration_ids: Type.Array(Type.String(), { minItems: 2 }),
  },
  closedObject,
);

const estimateRequirementsSchema = Type.Object(
  {
    model_parameters_b: Type.Number({ exclusiveMinimum: 0 }),
    usage: Type.Union([Type.Literal("inference"), Type.Literal("fine_tune")]),
    quantization: nullableString(),
    context_length: nullableInteger(1),
    concurrent_users: nullableInteger(1),
    training_method: nullableString(),
  },
  closedObject,
);

function normalizeToolApiBaseUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("invalid_tool_api_base_url");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username.length > 0 ||
    url.password.length > 0 ||
    url.search.length > 0 ||
    url.hash.length > 0
  ) {
    throw new Error("invalid_tool_api_base_url");
  }
  return url.toString().replace(/\/+$/, "");
}

export async function executeToolApi(
  toolName: ToolName,
  args: Record<string, unknown>,
  config: ToolApiConfig,
  callerSignal?: AbortSignal,
): Promise<JsonValue> {
  const baseUrl = normalizeToolApiBaseUrl(config.toolApiBaseUrl);
  const signal = callerSignal
    ? AbortSignal.any([callerSignal, AbortSignal.timeout(30_000)])
    : AbortSignal.timeout(30_000);

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/tools/${toolName}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(args),
      signal,
    });
  } catch {
    throw new Error("lab2_tool_api_unavailable");
  }

  if (!response.ok) {
    throw new Error(`lab2_tool_api_http_${response.status}`);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("lab2_tool_api_invalid_response");
  }
  if (
    payload === null ||
    typeof payload !== "object" ||
    typeof (payload as { ok?: unknown }).ok !== "boolean"
  ) {
    throw new Error("lab2_tool_api_invalid_response");
  }
  return payload as JsonValue;
}

export default defineToolPlugin({
  id: "lab2-catalog-tools",
  name: "Lab 2 Catalog Tools",
  description: "Allow-listed structured catalog and product-document tools for the Lab 2 demo.",
  configSchema: toolApiConfigSchema,
  tools: (tool) => [
    tool({
      name: "search_products",
      label: "Search products",
      description: "Search the structured product catalog using the supplied filters.",
      parameters: searchProductsSchema,
      async execute(params, config, context) {
        return executeToolApi("search_products", params, config, context.signal);
      },
    }),
    tool({
      name: "get_product",
      label: "Get product",
      description: "Retrieve a structured catalog product by its exact product ID.",
      parameters: getProductSchema,
      async execute(params, config, context) {
        return executeToolApi("get_product", params, config, context.signal);
      },
    }),
    tool({
      name: "search_product_documents",
      label: "Search product documents",
      description: "Search mapped product documents and return grounded document evidence.",
      parameters: searchDocumentsSchema,
      async execute(params, config, context) {
        return executeToolApi("search_product_documents", params, config, context.signal);
      },
    }),
    tool({
      name: "compare_products",
      label: "Compare products",
      description: "Compare exact catalog records for the requested product IDs.",
      parameters: compareProductsSchema,
      async execute(params, config, context) {
        return executeToolApi("compare_products", params, config, context.signal);
      },
    }),
    tool({
      name: "compare_configurations",
      label: "Compare configurations",
      description: "Compare configuration IDs when a configuration repository is configured.",
      parameters: compareConfigurationsSchema,
      async execute(params, config, context) {
        return executeToolApi("compare_configurations", params, config, context.signal);
      },
    }),
    tool({
      name: "estimate_ai_requirements",
      label: "Estimate AI requirements",
      description: "Run the deterministic Lab 2 sizing estimate for the provided requirements.",
      parameters: estimateRequirementsSchema,
      async execute(params, config, context) {
        return executeToolApi("estimate_ai_requirements", params, config, context.signal);
      },
    }),
  ],
});
