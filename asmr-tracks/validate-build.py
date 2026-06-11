#!/usr/bin/env python3
"""
Queen's Empire Audio Pipeline — Post-Build Validator
Run after ANY track build. Validates output integrity.
Exit code 1 = track is broken, needs rebuild.
"""
import sys, os, subprocess, json

def get_duration(filepath):
    """Get audio duration in seconds."""
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', filepath],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except:
        return None

def get_loudness(filepath):
    """Get integrated loudness in LUFS using ffmpeg loudnorm filter."""
    import re
    result = subprocess.run(
        ['ffmpeg', '-i', filepath,
         '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
         '-f', 'null', '/dev/null'],
        capture_output=True, text=True
    )
    try:
        # loudnorm JSON fragment goes to stderr — parse with regex
        match = re.search(r'"input_i"\s*:\s*"([-\d.]+)"', result.stderr)
        if match:
            return float(match.group(1))
    except:
        pass
    return None

def check_extracted_text(build_dir, num_segments=6):
    """Verify no script directions leaked into voice text."""
    leaks = []
    leak_patterns = [
        (r'FRACTIONATION\s*MOMENT', 'FRACTIONATION'),
        (r'\[Silence\s*[—–-]', '[Silence]'),
    ]
    for i in range(1, num_segments + 1):
        voice_file = os.path.join(build_dir, f'voice-{i}.txt')
        if not os.path.exists(voice_file):
            leaks.append(f'Voice {i} text file missing')
            continue
        with open(voice_file) as f:
            text = f.read()
        for pattern, name in leak_patterns:
            import re
            if re.search(pattern, text):
                leaks.append(f'Voice {i}: LEAK — {name} marker in spoken text')
    return leaks

def check_file_health(filepath):
    """Basic file integrity check."""
    issues = []
    if not os.path.exists(filepath):
        issues.append('File does not exist')
        return issues
    size = os.path.getsize(filepath)
    if size < 1024 * 1024:  # less than 1MB
        issues.append(f'File suspiciously small: {size/1024:.0f}KB')
    if size > 25 * 1024 * 1024:  # over 25MB
        issues.append(f'File unusually large: {size/1024/1024:.0f}MB')
    return issues

def main():
    if len(sys.argv) < 2:
        print("Usage: validate-build.py <track_mp3> [build_dir]")
        sys.exit(1)
    
    track_file = sys.argv[1]
    build_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    errors = []
    warnings = []
    
    # 1. File health
    health = check_file_health(track_file)
    errors.extend(health)
    
    # 2. Duration check
    dur = get_duration(track_file)
    if dur is None:
        errors.append('Cannot read duration — file may be corrupt')
    elif dur < 300:  # under 5 min
        errors.append(f'Duration too short: {dur:.0f}s ({dur/60:.1f}min)')
    elif dur < 360:  # under 6 min
        warnings.append(f'Duration shorter than target: {dur:.0f}s ({dur/60:.1f}min)')
    elif dur > 720:  # over 12 min
        warnings.append(f'Duration longer than target: {dur:.0f}s ({dur/60:.1f}min)')
    else:
        print(f'  Duration: {dur:.0f}s ({dur/60:.1f}min) ✓')
    
    # 3. Loudness
    loudness = get_loudness(track_file)
    if loudness:
        print(f'  Integrated loudness: {loudness:.1f} LUFS')
        if loudness < -22:
            errors.append(f'Track is too quiet: {loudness:.1f} LUFS — likely not normalized (target: -16)')
        elif loudness < -19:
            warnings.append(f'Track is quiet: {loudness:.1f} LUFS (target: -16)')
        elif loudness > -10:
            warnings.append(f'Track is loud: {loudness:.1f} LUFS (target: -16)')
    else:
        warnings.append('Could not measure loudness')
    
    # 4. Text leak check
    if build_dir and os.path.isdir(build_dir):
        text_leaks = check_extracted_text(build_dir)
        errors.extend(text_leaks)
        if not text_leaks:
            print('  Voice text: clean ✓')
    
    # Report
    print()
    if errors:
        print(f'❌ FAILED: {len(errors)} error(s)')
        for e in errors:
            print(f'   🔴 {e}')
        sys.exit(1)
    
    if warnings:
        print(f'⚠️  PASSED with {len(warnings)} warning(s)')
        for w in warnings:
            print(f'   🟡 {w}')
    else:
        print('✅ All checks passed.')
    
    sys.exit(0)

if __name__ == '__main__':
    main()
