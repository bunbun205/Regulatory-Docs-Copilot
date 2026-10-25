/** Binary uploads use FormData while OpenAPI represents binary fields as strings. */
export function multipart(body: object, file: File | null): FormData {
  const form = new FormData();
  for (const [name, value] of Object.entries(body)) {
    if (value === null || value === undefined) continue;
    if (name === 'file' && file) form.append(name, file);
    else form.append(name, String(value));
  }
  return form;
}
