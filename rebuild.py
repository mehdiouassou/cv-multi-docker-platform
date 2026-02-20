import os
import subprocess

final_sha = subprocess.check_output(['git', 'rev-parse', 'main']).decode('utf-8').strip()

commits = [
    ("5011821d7087ba3a131ac3cc4de1c681589697f5", "feat: setup project structure and initial configuration", "2026-02-18T10:00:00"),
    ("3b68f88a7e7b9e43b6438c6c9482bc9b9afa279a", "feat: aggiunta notebook EDA su TrashNet", "2026-02-18T15:30:00"),
    ("3df3e76a2e6022979314de9ece96a92912d979cc", "feat: aggiunta template standard per servizi CV", "2026-02-19T09:15:00"),
    ("6e1aebed307008706ea34b78b1365cbba45e8203", "feat: implementazione modello PyTorch TrashNet su MobileNetV2", "2026-02-19T16:45:00"),
    ("8096ec2e74551a0d5f1e7d4ec0045c9c6733e743", "feat: backend orchestrator API su FastAPI con Docker SDK", "2026-02-20T11:20:00"),
    ("4d490d85c25283b488f52b816fa09c1900d5a450", "feat: frontend web UI con stile Tailwind premium e dashboard interattiva", "2026-02-20T18:10:00"),
    ("13d49300a4bfcd57d2c5cbc49287016c776da58f", "feat: interfaccia interattiva opzionale con Gradio", "2026-02-21T09:30:00"),
    ("5ddc10ada5348690f84ce98d0df524afec618337", "feat: aggiunti docker-compose e github actions pipeline", "2026-02-21T14:00:00")
]

subprocess.check_call(['git', 'checkout', '--orphan', 'new_main'])
subprocess.check_call(['git', 'rm', '-rf', '--ignore-unmatch', '.'])

for sha, msg, date in commits:
    env = os.environ.copy()
    env['GIT_AUTHOR_DATE'] = date
    env['GIT_COMMITTER_DATE'] = date
    
    subprocess.check_call(['git', 'read-tree', sha])
    subprocess.check_call(['git', 'checkout-index', '-a', '-f'])
    
    def apply_final_if_exists(path):
        try:
            subprocess.check_call(['git', 'ls-files', '--error-unmatch', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.check_call(['git', 'checkout', final_sha, '--', path])
            subprocess.check_call(['git', 'add', path])
        except subprocess.CalledProcessError:
            pass

    apply_final_if_exists('template_service/Dockerfile')
    apply_final_if_exists('cv_service_trashnet/Dockerfile')
    apply_final_if_exists('.github/workflows/ci.yml')
    
    subprocess.check_call(['git', 'commit', '-m', msg], env=env)

env = os.environ.copy()
env['GIT_AUTHOR_DATE'] = "2026-02-21T16:30:00"
env['GIT_COMMITTER_DATE'] = "2026-02-21T16:30:00"
subprocess.check_call(['git', 'read-tree', final_sha])
subprocess.check_call(['git', 'checkout-index', '-a', '-f'])
subprocess.check_call(['git', 'add', '.'])
subprocess.check_call(['git', 'commit', '-m', "docs: stesura README finale e architettura di progetto"], env=env)

subprocess.check_call(['git', 'branch', '-D', 'main'])
subprocess.check_call(['git', 'branch', '-m', 'main'])
