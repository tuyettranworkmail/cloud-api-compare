import { request, summary, optionsFor } from './common.js';
export const options = optionsFor('steady');
export default function () { request('cpu'); }
export const handleSummary = summary;
