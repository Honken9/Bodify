/** Krymp ett foto innan uppladdning — mobilkameror ger 10+ MP vilket gör
 * AI-analysen mångdubbelt långsammare utan att träffsäkerheten blir bättre.
 * Max 1280 px på längsta sidan och JPEG ~85 % räcker gott för vision-modellen. */
export async function downscaleImage(
  file: Blob,
  maxDim = 1280,
  quality = 0.85
): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    return await new Promise<Blob>((resolve) =>
      canvas.toBlob(
        (blob) => resolve(blob ?? file),
        "image/jpeg",
        quality
      )
    );
  } catch {
    return file; // äldre webbläsare utan stöd → skicka originalet
  }
}
