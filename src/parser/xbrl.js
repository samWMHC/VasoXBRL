import { XMLParser } from "fast-xml-parser";

const DEFAULT_PARSER_OPTS = {
  ignoreAttributes: false,
  attributeNamePrefix: "@_",
  removeNSPrefix: true,
};

export class XbrlParser {
  constructor(opts = {}) {
    this.xml = new XMLParser({ ...DEFAULT_PARSER_OPTS, ...opts });
  }

  /** Parse raw XBRL/XML text into a JS object tree. */
  parse(xmlText) {
    return this.xml.parse(xmlText);
  }

  /** Extract all XBRL facts (contextRef + value) from a parsed document. */
  extractFacts(parsed) {
    const facts = [];
    this._walk(parsed, (key, value) => {
      if (value && typeof value === "object" && value["@_contextRef"]) {
        facts.push({
          concept: key,
          contextRef: value["@_contextRef"],
          unitRef: value["@_unitRef"] || null,
          decimals: value["@_decimals"] || null,
          value: value["#text"] ?? null,
        });
      }
    });
    return facts;
  }

  /** List the contexts defined in the filing. */
  extractContexts(parsed) {
    const xbrl = parsed.xbrl || parsed.html?.body?.xbrl || parsed;
    const raw = xbrl.context;
    if (!raw) return [];

    const contexts = Array.isArray(raw) ? raw : [raw];
    return contexts.map((ctx) => ({
      id: ctx["@_id"],
      entity: ctx.entity?.identifier?.["#text"] || null,
      period: ctx.period || null,
    }));
  }

  _walk(obj, visitor) {
    if (obj == null || typeof obj !== "object") return;
    for (const [key, value] of Object.entries(obj)) {
      visitor(key, value);
      if (Array.isArray(value)) {
        value.forEach((item) => {
          visitor(key, item);
          this._walk(item, visitor);
        });
      } else {
        this._walk(value, visitor);
      }
    }
  }
}
