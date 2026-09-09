"""Read complete gzip streams and check archive roots before uploading."""
import gzip
import json
from pathlib import Path
import sys
import tarfile

for name in sys.argv[1:]:
    path = Path(name)
    members = {}
    manifest = None
    with gzip.open(path, 'rb') as stream:
        with tarfile.open(fileobj=stream, mode='r|') as archive:
            for member in archive:
                key = member.name.removeprefix('./')
                members[key] = member.size
                assert not Path(key).is_absolute() and '..' not in Path(key).parts, key
                assert Path(key).name != '.env' and not Path(key).name.startswith('.env.'), key
                if key == 'manifest.json':
                    manifest = json.load(archive.extractfile(member))
        while stream.read(1024 * 1024):
            pass  # Consume the gzip trailer and validate CRC, including trailing data.
    if path.name == 'model.tar.gz':
        for folder in ('gemma-4-E2B-it', 'embedding_model'):
            assert f'{folder}/config.json' in members, folder
            assert any(k.startswith(folder + '/') and k.endswith('.safetensors') for k in members), folder
        for source in Path('model').rglob('*'):
            if source.is_file():
                key = source.relative_to('model').as_posix()
                assert members.get(key) == source.stat().st_size, key
    else:
        assert manifest and len(manifest) == 1
        for entry in manifest:
            assert entry['Config'] in members
            assert entry['Layers'] and all(layer in members for layer in entry['Layers'])
    print(json.dumps({'archive': path.name, 'bytes': path.stat().st_size,
                      'members': len(members), 'gzip_integrity': 'passed', 'layout': 'passed'}), flush=True)
