using UnityEngine;
using TMPro;
using System.Collections;

public class MatchIndicator : MonoBehaviour
{
    int time;
    [SerializeField] TMP_Text timer;
    [SerializeField] TMP_Text indicator;

    void OnEnable()
    {
        time = 0;
        
        StartCoroutine(Clock());
    }

    void OnDisable()
    {
        StopAllCoroutines();
    }

    IEnumerator Clock()
    {
        var wait = new WaitForSeconds(1);

        while (true)
        {
            timer.text = string.Format("{0:D2}:{1:D2}", time/60, time%60);
            indicator.text = "매칭중" + new string('.', time%4);

            time++;

            yield return wait;
        }
    }
}
