export interface EmailMessage {
  to: string;
  subject: string;
  text: string;
}

/** Format a message; the caller handles delivery. */
export function createEmail(to: string, subject: string, text: string): EmailMessage {
  return { to, subject, text };
}
