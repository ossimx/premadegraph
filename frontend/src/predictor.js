const OPENROUTER_API_KEY = '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';

const fetchCountryByName = async (playerName) => {
  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${OPENROUTER_API_KEY}`,
        "HTTP-Referer": "localhost",
        "X-Title": "MyAppName",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash-preview-05-20",
        messages: [
          {
            role: "system",
            content: [
              {
                type: "text",
                text: "We are in Eastern-nordic europe. You are an expert in identifying the likely country or region of origin based on player names.",
              },
            ],
          },
          {
            role: "user",
            content: [
              {
                type: "text",
                text: `Player name: ${playerName}\nWhat is the most likely country or region this player comes from? Please answer with just the country or region name.`,
              },
            ],
          },
        ],
        max_tokens: 20,
        temperature: 0.3,
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error(`OpenRouter API hiba: ${response.status} - ${errText}`);
      return null;
    }

    const data = await response.json();
    const answer = data.choices?.[0]?.message?.content?.trim() || null;
    return answer;
  } catch (error) {
    console.error("OpenRouter fetch hiba:", error);
    return null;
  }
};

(async () => {
  const playerName = "KovacsPeter";
  const country = await fetchCountryByName(playerName);
  console.log(`A játékos név: ${playerName}, valószínűsíthető régió: ${country}`);
})();