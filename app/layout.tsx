import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'MentalCore Mastery PDF',
  description:
    'MentalCore YouTube premium PDF for focus, discipline, and emotional resilience.'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
