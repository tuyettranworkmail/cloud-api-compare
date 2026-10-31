import { request, summary, optionsFor } from './common.js';
export const options = optionsFor('burst');
export default function () { request(); }
export const handleSummary = summary;
