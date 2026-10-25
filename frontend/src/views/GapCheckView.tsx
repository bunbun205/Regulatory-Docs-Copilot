import { useParams } from 'react-router-dom';
import GapInput from '../components/gap/GapInput';
import GapJob from '../components/gap/GapJob';

export default function GapCheckView() {
  const { jobId } = useParams();
  return jobId ? <GapJob key={jobId} jobId={jobId} /> : <GapInput />;
}
