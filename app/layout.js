import './globals.css';

export const metadata = {
  title: 'MentalCore Mastery PDF | Rewire Focus & Confidence',
  description:
    'Official MentalCore YouTube channel guide. High-performance mental framework in one actionable PDF.'
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
