using System;
using UnityEngine;

namespace core.Sound
{
    [Serializable]
    public class BgmEntry
    {
        public BgmKey key;
        public AudioClip clip;
    }
    
    [Serializable]
    public class SfxEntry
    {
        public SfxKey key;
        public AudioClip clip;
    }
}