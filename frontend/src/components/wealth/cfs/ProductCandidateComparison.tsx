import type { CFSProductCompositionResponse } from "../../../api/productOntology";
import { CFSProductCandidates } from "../CFSProductCandidates";

export function ProductCandidateComparison({ composition }: { composition: CFSProductCompositionResponse }) {
  return <CFSProductCandidates composition={composition} />;
}
