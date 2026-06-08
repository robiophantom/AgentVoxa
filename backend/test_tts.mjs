import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
import 'dotenv/config';

console.log(process.env.ELEVENLABS_API_KEY ? "Key exists" : "No key");

const client = new ElevenLabsClient({
  apiKey: process.env.ELEVENLABS_API_KEY,
});
// Let's hook into fetch to see what it sends
const originalFetch = global.fetch;
global.fetch = async (url, options) => {
  console.log("URL:", url);
  console.log("Method:", options.method);
  console.log("Body:", options.body);
  return originalFetch(url, options);
};

async function main() {
  try {
    const response = await client.textToSpeech.convert(
      "21m00Tcm4TlvDq8ikWAM",
      {text: "This is a test for the API of ElevenLabs."}
    );
    console.log("Success");
  } catch (e) {
    console.error(e);
  }
}
main();
