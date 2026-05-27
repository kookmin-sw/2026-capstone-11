using System;
using UnityEngine;
using UnityEngine.Audio;
using System.Collections.Generic;

namespace core.Sound
{
    [Serializable]
    public enum BgmKey
    {
        Title,
        MainMenu,
        Battle,
    }

    [Serializable]
    public enum SfxKey
    {
        ButtonClick,
    }

    public class SoundManager : MonoBehaviour
    {
        [Header("Audio Sources")]
        public AudioSource bgmPlayer;
        public BgmEntry[] bgmClips;

        public AudioSource[] sfxPlayer;
        public SfxEntry[] sfxClips;

        [Header("Audio Mixer")]
        public AudioMixer audioMixer;

        private const string KEY_MUTE_BGM = "IsMuted_bgm";
        private const string KEY_MUTE_SFX = "IsMuted_sfx";
        private const string KEY_VOL_BGM  = "Volume_BGM";
        private const string KEY_VOL_SFX  = "Volume_SFX";

        private int sfxCursor;

        public static SoundManager Instance;

        private Dictionary<BgmKey, AudioClip> bgmDict = new();
        private Dictionary<SfxKey, AudioClip> sfxDict = new();

        public void Init()
        {
            if (Instance != null)
            {
                Destroy(gameObject);
                return;
            }

            Instance = this;

            InitializeFromPrefs();
            RegisterClips();
        }

        // ===== Init / Apply =====
        public void InitializeFromPrefs()
        {
            // 기본값 보장
            if (!PlayerPrefs.HasKey(KEY_MUTE_BGM)) PlayerPrefs.SetInt(KEY_MUTE_BGM, 0);
            if (!PlayerPrefs.HasKey(KEY_MUTE_SFX)) PlayerPrefs.SetInt(KEY_MUTE_SFX, 0);

            if (!PlayerPrefs.HasKey(KEY_VOL_BGM)) PlayerPrefs.SetFloat(KEY_VOL_BGM, 0.3f);
            if (!PlayerPrefs.HasKey(KEY_VOL_SFX)) PlayerPrefs.SetFloat(KEY_VOL_SFX, 1.0f);

            ApplyFromPrefs();
        }

        public void ApplyFromPrefs()
        {
            bool muteBgm = PlayerPrefs.GetInt(KEY_MUTE_BGM, 0) == 1;
            bool muteSfx = PlayerPrefs.GetInt(KEY_MUTE_SFX, 0) == 1;

            float vBgm = PlayerPrefs.GetFloat(KEY_VOL_BGM, 0.3f);
            float vSfx = PlayerPrefs.GetFloat(KEY_VOL_SFX, 1.0f);

            if (vBgm <= 0.0001f) 
                vBgm = 0.0001f; // 로그 계산 방지
            if (vSfx <= 0.0001f)
                vSfx = 0.0001f; // 로그 계산 방지

            audioMixer.SetFloat("BGM", Mathf.Log10(vBgm) * 20);
            audioMixer.SetFloat("SFX", Mathf.Log10(vSfx) * 20);

            bgmPlayer.mute = muteBgm;
            MuteSfxSources(muteSfx);
        }

        private void RegisterClips()
        {
            foreach (var entry in bgmClips)
            {
                if (!bgmDict.ContainsKey(entry.key))
                    bgmDict.Add(entry.key, entry.clip);
            }

            foreach (var entry in sfxClips)
            {
                if (!sfxDict.ContainsKey(entry.key))
                    sfxDict.Add(entry.key, entry.clip);
            }
        }

        private void MuteSfxSources(bool mute)
        {
            foreach (var source in sfxPlayer)
            {
                source.mute = mute;
            }
        }

        // ===== BGM =====
        public void PlayBgm(BgmKey bgmKey)
        {
            if (!bgmDict.ContainsKey(bgmKey)) 
                return;

            bgmPlayer.clip = bgmDict[bgmKey];

            if (!bgmPlayer.isPlaying) bgmPlayer.Play();
        }

        public void StopBgm()
        {
            if (bgmPlayer.isPlaying) bgmPlayer.Stop();
        }

        // ===== SFX =====
        public void PlaySfx(SfxKey type)
        {
            AudioClip clip = null;

            foreach (var entry in sfxClips)
            {
                if (entry.key == type)
                {
                    clip = entry.clip;
                    break;
                }
            }   

            sfxPlayer[sfxCursor].PlayOneShot(clip);
            sfxCursor = (sfxCursor + 1) % sfxPlayer.Length;

            Debug.Log("효과음 재생됨");
        }

        // ===== Settings (UI에서 호출) =====
        public void SetMuteBgm(bool mute)
        {
            PlayerPrefs.SetInt(KEY_MUTE_BGM, mute ? 1 : 0);
            PlayerPrefs.Save();
            ApplyFromPrefs();
        }

        public void SetMuteSfx(bool mute)
        {
            PlayerPrefs.SetInt(KEY_MUTE_SFX, mute ? 1 : 0);
            PlayerPrefs.Save();
            ApplyFromPrefs();
        }

        public void SetVolumeBgm(float v)
        {
            PlayerPrefs.SetFloat(KEY_VOL_BGM, Mathf.Clamp01(v));
            PlayerPrefs.Save();
            ApplyFromPrefs();
        }

        public void SetVolumeSfx(float v)
        {
            PlayerPrefs.SetFloat(KEY_VOL_SFX, Mathf.Clamp01(v));
            PlayerPrefs.Save();
            ApplyFromPrefs();
        }
    }
}