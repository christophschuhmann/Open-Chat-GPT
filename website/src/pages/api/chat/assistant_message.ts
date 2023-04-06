import { boolean } from "boolean";
import { withoutRole } from "src/lib/auth";
import { createInferenceClient } from "src/lib/oasst_inference_client";
import { InferencePostAssistantMessageParams } from "src/types/Chat";

const handler = withoutRole("banned", async (req, res, token) => {
  if (!boolean(process.env.ENABLE_CHAT)) {
    return res.status(404).end();
  }
  const client = createInferenceClient(token);

  const data = await client.post_assistant_message(req.body as InferencePostAssistantMessageParams);

  if (data) {
    return res.status(200).json(data);
  }
  res.status(400).end();
});

export default handler;
