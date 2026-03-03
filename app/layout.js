import './globals.css';
import { SpeedInsights } from '@vercel/speed-insights/next';

export const metadata = {
  title: 'MentalCore Mastery PDF | Rewire Focus & Confidence',
  description:
    'Official MentalCore YouTube channel guide. High-performance mental framework in one actionable PDF.'
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
        <SpeedInsights />
      </body>
    </html>
  );
}
