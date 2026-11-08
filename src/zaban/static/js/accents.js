// English accents the learner can practise. Niko's voice and the learner's speech recognition use the chosen one.
// Voices come from the browser and operating system, so a missing voice is reported on the page, not hidden.
const Accents = (() => {
  const LIST = [
    {
      code: "en-US",
      name: Z.tr("امریکایی"),
      nameEn: "American",
      sample: "Hi there! I'm Niko. Let's practice together. What did you do today?",
      voices: ["Aria", "Jenny", "Zira", "Guy", "Google US English"],
    },
    {
      code: "en-GB",
      name: Z.tr("بریتانیایی"),
      nameEn: "British",
      sample: "Hello! I'm Niko. Shall we have a little chat? How was your day?",
      voices: ["Sonia", "Libby", "Hazel", "Google UK English Female", "Google UK English Male"],
    },
    {
      code: "en-AU",
      name: Z.tr("استرالیایی"),
      nameEn: "Australian",
      sample: "G'day! I'm Niko. Let's have a yarn about your day.",
      voices: ["Natasha", "Annette", "Catherine"],
    },
    {
      code: "en-CA",
      name: Z.tr("کانادایی"),
      nameEn: "Canadian",
      sample: "Hi! I'm Niko. Let's chat a bit. How was your day?",
      voices: ["Clara", "Linda"],
    },
  ];

  let current = "en-US";

  function voiceFor(code) {
    if (!("speechSynthesis" in window)) return null;
    const item = LIST.find((a) => a.code === code);
    const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.replace("_", "-").toLowerCase() === code.toLowerCase());
    if (!item) return voices[0] || null;
    // Prefer the named voices, because they sound most natural. Otherwise use any voice in that accent.
    for (const name of item.voices) {
      const found = voices.find((v) => v.name.includes(name));
      if (found) return found;
    }
    return voices[0] || null;
  }

  // Plays the sample sentence in that accent. Returns false when the device has no voice for it.
  function speakSample(code) {
    const item = LIST.find((a) => a.code === code);
    const voice = voiceFor(code);
    if (!item || !voice) return false;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(item.sample);
    utterance.lang = code;
    utterance.voice = voice;
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
    return true;
  }

  return {
    LIST,
    get current() { return current; },
    setCurrent(code) { current = code; },
    voiceFor,
    speakSample,
  };
})();
