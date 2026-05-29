using UnityEngine;

namespace Animations
{    
    public class VFXHandler : MonoBehaviour
    {
        [Header("Prefabs")]
        public GameObject deployEffect;
        public GameObject lightEffect;
        public GameObject hitEffect;
        public GameObject moveEffect;
        public GameObject healEffect;

        public void PlayDeploy(Vector3 position)
        {
            Instantiate(deployEffect, position, Quaternion.identity);
        }

        public void PlayEyeLight(Vector3 position)
        {
            Instantiate(lightEffect, position, Quaternion.identity);
        }

        public void PlayHit(Vector3 position)
        {
            Instantiate(hitEffect, position + new Vector3(0.25f, 0.25f), Quaternion.identity);
        }

        public void PlayMove(Vector3 position)
        {
            Instantiate(moveEffect, position, Quaternion.identity);
        }

        public void PlayHeal(Vector3 position)
        {
            for(int i=0;i<5;i++)
            {
                var offset = Random.insideUnitCircle * 0.5f;

                Instantiate(
                    healEffect,
                    position + (Vector3)offset,
                    Quaternion.identity
                );
            }
        }
    }
}
