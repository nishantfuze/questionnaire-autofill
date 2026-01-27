import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Questionnaire Autofill',
  description: 'Automatically fill bank questionnaires with answers from the knowledge base',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  );
}
