export const MARKETING_PREVIEW = Object.freeze({
  token: Object.freeze({symbol: "SIGNAL", address: "0x71A4…C92F", score: 72}),
  signals: Object.freeze([
    Object.freeze({label: "Linked wallets", value: "4 clusters", band: "review"}),
    Object.freeze({label: "Fresh-wallet supply", value: "18.4%", band: "watch"}),
    Object.freeze({label: "Sniper concentration", value: "6.2%", band: "clear"}),
  ]),
  plans: Object.freeze([
    Object.freeze({id: "sandbox", name: "Sandbox", price: "$0", note: "Representative development access", limits: Object.freeze(["3 requests / minute", "10-request burst", "Cached preview results"])}),
    Object.freeze({id: "developer", name: "Developer", price: "$49 / month", note: "Temporary planning example", limits: Object.freeze(["50 requests / minute", "One token-risk integration", "Email support preview"]), recommended: true}),
    Object.freeze({id: "team", name: "Team", price: "$199 / month", note: "Temporary planning example", limits: Object.freeze(["100 requests / minute", "10 token-risk integrations", "Priority support preview"])}),
    Object.freeze({id: "scale", name: "Scale", price: "$499 / month", note: "Temporary planning example", limits: Object.freeze(["500 requests / minute", "Bulk report preview", "Dedicated support preview"])}),
  ]),
});
