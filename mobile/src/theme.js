import { Platform } from 'react-native';

// Colours taken from the Figma design.
export const colors = {
  page: '#E3ECE7',      // background around the "phone" in the browser
  bg: '#EEF5F1',        // app background
  card: '#FFFFFF',
  primary: '#2F5E4E',   // dark green: buttons, patient bubbles
  primarySoft: '#DDEBE3',
  text: '#1D2B25',
  muted: '#6E7F78',
  border: '#D5E3DB',
  avatar: '#8FBFA5',
  online: '#4CAF7A',
  error: '#B3412F',
};

// Serif font for headings, like "Good morning, James." in the design.
export const serif = Platform.select({
  web: 'Georgia, "Times New Roman", serif',
  ios: 'Georgia',
  default: 'serif',
});