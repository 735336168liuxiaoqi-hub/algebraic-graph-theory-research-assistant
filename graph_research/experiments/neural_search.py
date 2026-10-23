"""Independent CPU autoregressive CEM implementation, optional PyTorch only.

Algorithm reference: cema-for-graphs. No upstream source is copied. Sparse
observations are reconstructed from action sequences; no O(batch*L^2) array,
Java reward bridge, pickle checkpoints, TensorBoard, or CUDA requirement.
"""
import array
import base64
import math
import sys

from .search_space import decisions


class Policy:
    def __init__(self,domain,seed,state=None):
        try:import torch
        except ImportError:raise ValueError('cem需要可选PyTorch CPU环境；请安装search extra或选择random/local/enumerate。') from None
        self.torch=torch;self.domain=domain
        torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.manual_seed(seed)
        n=domain['n'];outputs=max(2,n,domain['max_edges']+1,len(domain['edge_sizes']))
        self.model=torch.nn.Sequential(torch.nn.Linear(2*n+4,16),torch.nn.Tanh(),torch.nn.Linear(16,outputs))
        self.velocity={name:torch.zeros_like(p) for name,p in self.model.named_parameters()}
        self.updates=0
        if state is not None:
            if state.get('format')!='cpu-cem/1' or state.get('torch_version')!=torch.__version__ or state.get('byte_order')!=sys.byteorder:raise ValueError('CEM runtime/checkpoint version changed')
            if set(state['weights'])!=set(self.velocity) or set(state['momentum'])!=set(self.velocity):raise ValueError('CEM parameter inventory changed')
            with torch.no_grad():
                for name,p in self.model.named_parameters():
                    p.copy_(self._decode(state['weights'][name],p.shape));self.velocity[name]=self._decode(state['momentum'][name],p.shape)
            self.updates=state['updates']

    def _decode(self,data,shape):
        if data.get('shape')!=list(shape) or len(data.get('data',''))>128*1024:raise ValueError('CEM tensor shape/size invalid')
        raw=base64.b64decode(data['data'],validate=True);values=array.array('f')
        if len(raw)!=math.prod(shape)*4:raise ValueError('CEM tensor length invalid')
        values.frombytes(raw)
        if any(not math.isfinite(v) for v in values):raise ValueError('Nonfinite CEM checkpoint')
        return self.torch.tensor(values.tolist(),dtype=self.torch.float32).reshape(shape)

    @staticmethod
    def _encode(tensor):
        values=array.array('f',tensor.detach().flatten().tolist())
        return {'shape':list(tensor.shape),'data':base64.b64encode(values.tobytes()).decode('ascii')}

    def sample(self,rng,exploration):
        trajectory=[]
        def choose(features,legal):
            with self.torch.no_grad():probs=self.torch.softmax(self.model(self.torch.tensor(features))[legal],dim=0).tolist()
            action=rng.choice(legal) if rng.random()<exploration else rng.choices(legal,weights=probs,k=1)[0]
            trajectory.append(action);return action
        return decisions(self.domain,choose),trajectory

    def learn(self,trajectories):
        torch=self.torch;features=[];legal_masks=[];targets=[]
        def flush():
            if not targets:return
            self.model.zero_grad();logits=self.model(torch.tensor(features));mask=torch.zeros_like(logits,dtype=torch.bool)
            for i,legal in enumerate(legal_masks):mask[i,legal]=True
            logits=logits.masked_fill(~mask,-1e9);loss=torch.nn.functional.cross_entropy(logits,torch.tensor(targets));loss.backward()
            with torch.no_grad():
                for name,p in self.model.named_parameters():
                    grad=p.grad.clamp(-5,5);self.velocity[name].mul_(0.9).add_(grad);p.add_(self.velocity[name],alpha=-0.01)
            self.updates+=1;features.clear();legal_masks.clear();targets.clear()
        for trajectory in trajectories:
            cursor=0
            def replay(observation,legal):
                nonlocal cursor
                if cursor>=len(trajectory):raise ValueError('Truncated CEM trajectory')
                action=trajectory[cursor];cursor+=1
                if action not in legal:raise ValueError('Invalid CEM trajectory action')
                features.append(observation);legal_masks.append(legal);targets.append(action)
                if len(targets)>=64:flush()
                return action
            decisions(self.domain,replay)
            if cursor!=len(trajectory):raise ValueError('Extra CEM trajectory actions')
        flush()

    def state(self):
        return {'format':'cpu-cem/1','torch_version':self.torch.__version__,'byte_order':sys.byteorder,
            'weights':{name:self._encode(p) for name,p in self.model.named_parameters()},
            'momentum':{name:self._encode(p) for name,p in self.velocity.items()},'updates':self.updates}
